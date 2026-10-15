import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.db import get_session
from app.engine.cognitive_engine import CognitiveEngine
from app.models.user import User
from app.services.memory_service import MemoryService


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
            username="blueprint_tester",
            profile_data={},
        )
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
async def test_engine_extract_blueprint_from_text(session: Session):
    engine = CognitiveEngine()
    uid = uuid.UUID("44444444-4444-4444-4444-444444444444")

    sample_article = (
        "\u4e3a\u4ec0\u4e48 90% \u7684\u72ec\u7acb\u5f00\u53d1\u8005\u90fd\u8d5a\u4e0d\u5230\u94b1\uff1f"
        "\u56e0\u4e3a\u4ed6\u4eec\u4e00\u5f00\u59cb\u5c31\u60f3\u7740\u514d\u8d39\u83b7\u5ba2\u3002"
        "\u6211\u4eec\u5fc5\u987b\u6df1\u5165\u5256\u6790\u5546\u4e1a\u95ed\u73af\u7684\u6838\u5fc3\u77db\u76fe\u3002"
        "\u6700\u7ec8\uff0c\u7ed9\u51fa\u9ad8\u5ba2\u5355\u4ef7\u4ea7\u54c1\u7684\u7834\u5c40\u8def\u5f84\u3002"
    )

    result = await engine.extract_blueprint_from_text(
        content_or_url=sample_article,
        title="\u72ec\u7acb\u5f00\u53d1\u8005\u9ad8\u5ba2\u5355\u7834\u5c40\u6cd5",
        user_id=uid,
        session=session,
    )

    assert result["success"] is True
    bp = result.get("blueprint") or result
    assert "id" in bp
    assert bp["title"] == "\u72ec\u7acb\u5f00\u53d1\u8005\u9ad8\u5ba2\u5355\u7834\u5c40\u6cd5"
    assert "hook_style" in bp
    assert "structural_stages" in bp
    assert len(bp["structural_stages"]) >= 1
    assert "emotional_arc" in bp
    assert "pacing" in bp

    # Verify persisted in User.profile_data["benchmark_blueprints"]
    user = session.get(User, uid)
    blueprints = user.profile_data.get("benchmark_blueprints", [])
    assert len(blueprints) >= 1
    assert blueprints[0]["id"] == bp["id"]


def test_api_blueprint_extract_and_lifecycle(session: Session, client: TestClient):
    uid = "44444444-4444-4444-4444-444444444444"
    sample_article = (
        "\u7206\u6b3e\u6587\u7ae0\u5f00\u7bc7\uff1a\u4f60\u7684\u65f6\u95f4\u6b63\u5728\u88ab\u5783\u573e\u4fe1\u606f\u541e\u566e\u3002"
        "\u7b2c\u4e00\u6b65\uff0c\u7834\u9664\u4fe1\u606f\u8327\u623f\u3002"
        "\u7b2c\u4e8c\u6b65\uff0c\u5efa\u7acb\u7b2c\u4e8c\u5927\u8111\u3002"
        "\u7b2c\u4e09\u6b65\uff0c\u5f00\u542f\u9ad8\u6548\u751f\u4ea7\u529b\u3002"
    )

    # 1. Extract via API
    res_extract = client.post(
        "/api/blueprints/extract",
        json={
            "content": sample_article,
            "title": "\u7b2c\u4e8c\u5927\u8111\u7206\u6b3e\u6846\u67b6",
            "user_id": uid,
        },
    )
    assert res_extract.status_code == 200
    extract_data = res_extract.json()
    assert extract_data["success"] is True
    bp = extract_data.get("blueprint") or extract_data
    bp_id = bp["id"]
    assert bp["title"] == "\u7b2c\u4e8c\u5927\u8111\u7206\u6b3e\u6846\u67b6"

    # 2. List blueprints
    res_list = client.get(f"/api/blueprints?user_id={uid}")
    assert res_list.status_code == 200
    bps = res_list.json()
    assert any(b["id"] == bp_id for b in bps)

    # 3. Get single blueprint
    res_get = client.get(f"/api/blueprints/{bp_id}?user_id={uid}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == bp_id

    # 4. Delete blueprint
    res_del = client.delete(f"/api/blueprints/{bp_id}?user_id={uid}")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # 5. Verify 404 after deletion
    res_404 = client.get(f"/api/blueprints/{bp_id}?user_id={uid}")
    assert res_404.status_code == 404


def test_api_blueprint_validation_error(client: TestClient):
    # Missing content/text/url
    res = client.post("/api/blueprints/extract", json={"title": "Empty"})
    assert res.status_code == 422


def test_blueprint_update_api(session: Session, client: TestClient):
    """Verifies PUT /api/blueprints/{blueprint_id} allows editing blueprint metadata."""
    uid = "test-bp-user-002"

    # 1. Extract blueprint
    sample_text = """# 爆款文章测试
这是正文第一段，提出了核心问题。
深入分析背后的商业逻辑。
最后给出三点行动建议。"""
    res = client.post(
        "/api/blueprints/extract",
        json={"content": sample_text, "title": "初始测试骨架", "user_id": uid},
    )
    assert res.status_code == 200
    bp_id = res.json()["blueprint"]["id"]

    # 2. Update blueprint via PUT
    res_update = client.put(
        f"/api/blueprints/{bp_id}",
        json={
            "title": "已更新的爆款骨架",
            "hook_style": "悬念提问式Hook",
            "emotional_arc": "从焦虑到从容",
            "user_id": uid,
        },
    )
    assert res_update.status_code == 200
    updated_bp = res_update.json()
    assert updated_bp["title"] == "已更新的爆款骨架"
    assert updated_bp["hook_style"] == "悬念提问式Hook"
    assert updated_bp["emotional_arc"] == "从焦虑到从容"

    # 3. Fetch by ID to confirm persistence
    res_get = client.get(f"/api/blueprints/{bp_id}?user_id={uid}")
    assert res_get.status_code == 200
    assert res_get.json()["title"] == "已更新的爆款骨架"
