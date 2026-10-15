import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.auth import LOCAL_DEV_USER_ID
from app.core.db import get_session
from app.domain.cognitive.models import CognitiveProfile
from app.engine.cognitive_engine import CognitiveEngine, get_cognitive_engine
from app.models.user import User
from app.schemas.diff_schemas import DNAExtractionOutput, ThinkingDNA
from app.schemas.draft_schemas import DraftOutput
from app.schemas.outline_schemas import Outline, OutlineOutput, OutlineSection
from app.services.cognitive_service import CognitiveService


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(id=LOCAL_DEV_USER_ID, username="engine_tester")
        session.add(user)
        session.commit()
        session.refresh(user)
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_engine_explore_outlines_headless(session: Session):
    """Verifies CognitiveEngine executes headless outline generation with DNA."""
    engine = CognitiveEngine()
    user = session.exec(select(User)).first()
    
    mock_agent = MagicMock()
    mock_agent.generate_outlines = AsyncMock(
        return_value=OutlineOutput(
            outline_a=Outline(title="Approach A", rationale="Rat A", sections=[OutlineSection(title="S1")]),
            outline_b=Outline(title="Approach B", rationale="Rat B", sections=[OutlineSection(title="S2")]),
        )
    )
    
    res = await engine.explore_outlines(
        topic="Headless AI Architecture",
        user_id=user.id,
        agent=mock_agent,
        readonly_session=session,
    )
    
    assert res.outline_a.title == "Approach A"
    assert res.outline_b.title == "Approach B"
    mock_agent.generate_outlines.assert_called_once()


@pytest.mark.asyncio
async def test_engine_generate_draft_headless(session: Session):
    """Verifies CognitiveEngine generates full drafts headlessly."""
    engine = CognitiveEngine()
    user = session.exec(select(User)).first()
    
    mock_agent = MagicMock()
    mock_agent.generate_draft = AsyncMock(
        return_value=DraftOutput(
            title="AI Sandbox Draft",
            content="# AI Sandbox\nContent...",
            word_count=100,
        )
    )
    
    res = await engine.generate_draft(
        topic="AI Sandbox",
        outline={"title": "Sec", "rationale": "R", "sections": [{"title": "Part 1"}]},
        user_id=user.id,
        agent=mock_agent,
        readonly_session=session,
        session=session,
    )
    
    assert res.title == "AI Sandbox Draft"
    mock_agent.generate_draft.assert_called_once()


@pytest.mark.asyncio
async def test_engine_evolve_with_diff_zero_diff(session: Session):
    """Verifies zero-diff early return in engine."""
    engine = CognitiveEngine()
    mock_agent = MagicMock()
    mock_agent.extract_dna = AsyncMock(
        return_value=DNAExtractionOutput(
            has_diff=False,
            diff_summary="No modifications detected.",
        )
    )
    
    res = await engine.evolve_with_diff(
        original_ai_draft="Same content",
        user_final_draft="Same content",
        agent=mock_agent,
        session=session,
    )
    
    assert res.has_diff is False


def test_api_endpoints_ingest_and_skills(client: TestClient, session: Session):
    """Verifies FastAPI routes for own work, benchmark, dialogue clash, and skills."""
    user = session.exec(select(User)).first()
    
    # 1. GET /api/dna/skills
    res_skills = client.get("/api/dna/skills")
    assert res_skills.status_code == 200
    skills = res_skills.json()
    assert any(s["name"] == "media_article_extractor" for s in skills)
    assert any(s["name"] == "viewpoint_insight_miner" for s in skills)
    
    # 2. POST /api/dna/ingest-own-work
    res_own = client.post(
        "/api/dna/ingest-own-work",
        json={
            "content": "\u6211\u4eec\u5fc5\u987b\u575a\u6301\u81ea\u5e95\u5411\u4e0a\u9a8c\u8bc1\u3002\u6838\u5fc3\u5728\u4e8e\u4ee3\u7801\u8d28\u91cf\u9ad8\u4e8e\u4e00\u5207\u53e3\u53f7\u3002",
            "title": "Clean Code Manifesto",
            "user_id": str(user.id),
        },
    )
    assert res_own.status_code == 200
    data_own = res_own.json()
    assert data_own["success"] is True
    assert "mem0_actions" in data_own
    
    # 3. POST /api/dna/deconstruct-benchmark
    res_bench = client.post(
        "/api/dna/deconstruct-benchmark",
        json={
            "content": "\u672a\u6765\u5341\u5e74\u4f20\u7edf\u4ee3\u7801\u5c06\u5f7b\u5e95\u6d88\u5931\uff01\u6240\u6709\u8f6f\u4ef6\u90fd\u4f1a\u88abAI\u91cd\u5199\u3002",
            "title": "Radical AI Prediction",
            "user_id": str(user.id),
        },
    )
    assert res_bench.status_code == 200
    data_bench = res_bench.json()
    assert data_bench["success"] is True
    assert "blueprint" in data_bench
    assert "clash_points" in data_bench
    
    # 4. GET /api/dna/benchmarks
    res_list = client.get(f"/api/dna/benchmarks?user_id={user.id}")
    assert res_list.status_code == 200
    bench_list = res_list.json()
    assert len(bench_list) >= 1
    assert bench_list[0]["title"] == "Radical AI Prediction"
    
    # 5. POST /api/dna/dialogue-clash
    res_clash = client.post(
        "/api/dna/dialogue-clash",
        json={
            "messages": [
                {"role": "opponent", "content": "AI\u65f6\u4ee3\u5de5\u7a0b\u5e08\u4e0d\u518d\u9700\u8981\u61c2\u5e95\u5c42\u3002"},
                {"role": "user", "content": "\u6211\u5b8c\u5168\u53cd\u5bf9\u8fd9\u79cd\u76f2\u76ee\u4e50\u89c2\u3002\u4e0d\u61c2\u5e95\u5c42\u7684\u5de5\u7a0b\u5e08\u5728\u590d\u6742\u573a\u666f\u4e0b\u5fc5\u7136\u675f\u624b\u65e0\u7b56\u3002"},
            ],
            "debate_topic": "\u5e95\u5c42\u80fd\u529b\u4ef7\u503c",
            "user_id": str(user.id),
        },
    )
    assert res_clash.status_code == 200
    data_clash = res_clash.json()
    assert data_clash["success"] is True
    assert len(data_clash["recorded_stances"]) >= 1


def test_engine_ingest_and_dialogue_headless(session: Session):
    """Verifies CognitiveEngine executes own works, benchmark deconstruction, and dialogue clash headlessly."""
    engine = CognitiveEngine()
    user = session.exec(select(User)).first()

    # 1. Ingest own works headlessly
    res_own = engine.ingest_own_works_for_dna(
        content_or_url="我们在架构设计中必须坚决反对盲目重构。底层逻辑在于，最稳健的代码往往是自底向上演进而非一次性颠覆出来的。",
        user_id=user.id,
        title="My Headless Essay",
        session=session,
    )
    assert res_own["success"] is True
    assert "mem0_actions" in res_own

    # 2. Deconstruct benchmark article headlessly
    res_bench = engine.deconstruct_benchmark_article(
        content_or_url="未来五年传统单体架构将彻底死亡！所有企业都必须在今年全面淘汰旧技术。",
        user_id=user.id,
        title="External Viral Take",
        session=session,
    )
    assert res_bench["success"] is True
    assert "blueprint" in res_bench

    # 3. Ingest dialogue clash headlessly
    res_dialogue = engine.ingest_dialogue_and_evolve(
        messages=[
            {"role": "opponent", "content": "单体架构毫无前途。"},
            {"role": "user", "content": "我完全不同意，单体优先才是工程实践的最优解。"},
        ],
        user_id=user.id,
        debate_topic="架构演进",
        session=session,
    )
    assert res_dialogue["success"] is True
    assert len(res_dialogue["recorded_stances"]) >= 1
