"""Unit and integration tests for CognitiveService, Profile API, and Closed-Loop DNA Re-injection."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.db import get_session
from app.domain.cognitive.models import CognitiveDimension, TraitStatus
from app.models.user import User
from app.models.dna_record import DNARecord
from app.models.draft import Draft
from app.schemas.diff_schemas import ThinkingDNA
from app.schemas.outline_schemas import OutlineInput, OutlineOutput, Outline, OutlineSection
from app.schemas.draft_schemas import DraftInput, DraftOutput, CoreViewpoint
from app.services.cognitive_service import CognitiveService
from app.core.model_gateway import ModelGateway
from app.engine.agents.outline_agent import OutlineAgent
from app.engine.agents.draft_agent import DraftAgent


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# =====================================================================
# 1. CognitiveService Tests
# =====================================================================

def test_cognitive_service_bootstrap_from_dna_records(session: Session):
    # Setup user and historical DNA record
    user = User(username="alice", profile_data={})
    session.add(user)
    session.commit()
    session.refresh(user)

    rec = DNARecord(
        user_id=user.id,
        dna_data={
            "vocabulary_habits": ["非对称博弈", "第一性原理"],
            "logic_preferences": ["演绎递进", "逆向思维"],
            "core_values": ["长期主义", "关于「技术决定论」主张: 强烈反驳，组织惯性是关键"],
        },
    )
    session.add(rec)
    session.commit()

    profile = CognitiveService.get_or_create_user_profile(session, user.id)
    assert len(profile.traits) == 6
    assert any(t.statement == "非对称博弈" and t.dimension == CognitiveDimension.VOCABULARY for t in profile.traits)
    assert any(t.statement == "演绎递进" and t.dimension == CognitiveDimension.LOGIC_PREFERENCE for t in profile.traits)
    assert any(t.dimension == CognitiveDimension.VIEWPOINT_STANCE for t in profile.traits)


def test_cognitive_service_sync_and_reinforce(session: Session):
    user = User(username="bob", profile_data={})
    session.add(user)
    session.commit()
    session.refresh(user)

    dna1 = ThinkingDNA(
        vocabulary_habits=["穿透表象"],
        logic_preferences=["对比论证"],
        core_values=["价值驱动"],
    )
    CognitiveService.sync_extracted_dna(session, user.id, dna1)

    profile = CognitiveService.get_or_create_user_profile(session, user.id)
    trait = next(t for t in profile.traits if t.statement == "穿透表象")
    assert trait.confidence_score == 1.0

    # Reinforce with identical trait
    dna2 = ThinkingDNA(
        vocabulary_habits=["穿透表象"],
        logic_preferences=[],
        core_values=[],
    )
    CognitiveService.sync_extracted_dna(session, user.id, dna2)

    refreshed_profile = CognitiveService.get_or_create_user_profile(session, user.id)
    refreshed_trait = next(t for t in refreshed_profile.traits if t.statement == "穿透表象")
    assert refreshed_trait.confidence_score == 1.5


def test_cognitive_service_pin_unpin_suppress_delete(session: Session):
    user = User(username="carol", profile_data={})
    session.add(user)
    session.commit()
    session.refresh(user)

    trait = CognitiveService.add_custom_trait(
        session, CognitiveDimension.VOCABULARY, "降维打击", user_id=user.id
    )
    assert trait.status == TraitStatus.ACTIVE
    assert trait.confidence_score == 1.0

    # Pin
    pinned = CognitiveService.pin_trait(session, trait.id, user_id=user.id)
    assert pinned is not None
    assert pinned.status == TraitStatus.PINNED
    assert pinned.confidence_score == 2.0

    # Exportable DNA should include pinned trait
    dna = CognitiveService.get_exportable_dna_for_user(session, user.id)
    assert dna is not None
    assert "降维打击" in dna.vocabulary_habits

    # Suppress
    suppressed = CognitiveService.suppress_trait(session, trait.id, user_id=user.id)
    assert suppressed is not None
    assert suppressed.status == TraitStatus.SUPPRESSED

    # Exportable DNA should NOT include suppressed trait
    dna2 = CognitiveService.get_exportable_dna_for_user(session, user.id)
    assert dna2 is None or "降维打击" not in dna2.vocabulary_habits

    # Unpin
    unpinned = CognitiveService.unpin_trait(session, trait.id, user_id=user.id)
    assert unpinned is not None
    assert unpinned.status == TraitStatus.ACTIVE

    # Delete
    deleted = CognitiveService.delete_trait(session, trait.id, user_id=user.id)
    assert deleted is True
    profile = CognitiveService.get_or_create_user_profile(session, user.id)
    assert not any(t.id == trait.id for t in profile.traits)


# =====================================================================
# 2. Profile API Integration Tests
# =====================================================================

def test_api_profile_and_trait_lifecycle(client: TestClient, session: Session):
    # 1. GET /api/dna/profile (empty initially)
    resp = client.get("/api/dna/profile")
    assert resp.status_code == 200
    profile_data = resp.json()
    assert "traits" in profile_data

    # 2. POST /api/dna/traits (add custom trait)
    add_resp = client.post(
        "/api/dna/traits",
        json={"dimension": "vocabulary", "statement": "飞轮效应"},
    )
    assert add_resp.status_code == 200
    trait_obj = add_resp.json()
    trait_id = trait_obj["id"]
    assert trait_obj["statement"] == "飞轮效应"
    assert trait_obj["status"] == "active"

    # 3. POST /api/dna/traits/pin
    pin_resp = client.post("/api/dna/traits/pin", json={"trait_id": trait_id})
    assert pin_resp.status_code == 200
    assert pin_resp.json()["status"] == "pinned"

    # 4. POST /api/dna/traits/suppress
    sup_resp = client.post("/api/dna/traits/suppress", json={"trait_id": trait_id})
    assert sup_resp.status_code == 200
    assert sup_resp.json()["status"] == "suppressed"

    # 5. POST /api/dna/traits/unpin
    unpin_resp = client.post("/api/dna/traits/unpin", json={"trait_id": trait_id})
    assert unpin_resp.status_code == 200
    assert unpin_resp.json()["status"] == "active"

    # 6. DELETE /api/dna/traits/{trait_id}
    del_resp = client.delete(f"/api/dna/traits/{trait_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # 7. DELETE not found
    del_fail = client.delete(f"/api/dna/traits/{trait_id}")
    assert del_fail.status_code == 404


# =====================================================================
# 3. Closed-Loop DNA Re-injection Agent Tests
# =====================================================================

@pytest.mark.asyncio
async def test_outline_agent_dna_prompt_injection():
    # Verify that when thinking_dna is provided to OutlineAgent, it passes the formatted DNA into messages
    captured_messages = []

    mock_gateway = ModelGateway()
    async def mock_generate(*args, **kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return OutlineOutput(
            outline_a=Outline(title="Title A", rationale="Rat A", sections=[OutlineSection(title="Sec 1", bullet_points=["P1"])]),
            outline_b=Outline(title="Title B", rationale="Rat B", sections=[OutlineSection(title="Sec 2", bullet_points=["P2"])]),
        )

    mock_gateway.generate_structured = mock_generate
    agent = OutlineAgent(gateway=mock_gateway)

    dna = ThinkingDNA(
        vocabulary_habits=["心智模型", "逆势生长"],
        logic_preferences=["问题倒逼本质"],
        core_values=["激进务实"],
        summary="深刻、直切要害的认知风格",
    )

    inp = OutlineInput(topic="AI Native 时代的个人竞争力", thinking_dna=dna)
    result = await agent.generate_outlines(inp)

    assert result.outline_a.title == "Title A"
    assert len(captured_messages) == 1
    content = captured_messages[0]["content"]
    assert "=== USER'S COGNITIVE PROFILE & THINKING DNA" in content
    assert "心智模型" in content
    assert "问题倒逼本质" in content
    assert "激进务实" in content


@pytest.mark.asyncio
async def test_draft_agent_dna_prompt_injection():
    captured_messages = []

    mock_gateway = ModelGateway()
    async def mock_generate(*args, **kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return DraftOutput(
            title="AI 时代的个人认知护城河",
            summary="文章摘要",
            content="# AI 时代的个人认知护城河\n\n以心智模型穿透信息迷雾。",
            word_count=50,
            core_viewpoints=[CoreViewpoint(id="vp_1", claim="心智模型是第一壁垒", options=[])],
        )

    mock_gateway.generate_structured = mock_generate
    agent = DraftAgent(gateway=mock_gateway)

    dna = ThinkingDNA(
        vocabulary_habits=["穿透迷雾"],
        logic_preferences=["总分总演绎"],
        core_values=["非共识真理"],
    )

    chosen_outline = Outline(
        title="纲领", rationale="论证", sections=[OutlineSection(title="第一章", bullet_points=["要点一"])]
    )
    inp = DraftInput(topic="AI 护城河", outline=chosen_outline, thinking_dna=dna)
    draft = await agent.generate_draft(inp)

    assert draft.title == "AI 时代的个人认知护城河"
    assert len(captured_messages) == 1
    content = captured_messages[0]["content"]
    assert "=== USER'S COGNITIVE PROFILE & THINKING DNA" in content
    assert "穿透迷雾" in content
    assert "非共识真理" in content
