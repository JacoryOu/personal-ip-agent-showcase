import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.auth import LOCAL_DEV_USER_ID
from app.core.db import get_session
from app.domain.cognitive.models import CognitiveDimension, TraitStatus
from app.models.user import User
from app.services.cognitive_service import CognitiveService
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
            id=LOCAL_DEV_USER_ID,
            username="dna_tester",
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


def test_dna_crud_and_toggle(session: Session, client: TestClient):
    uid = str(LOCAL_DEV_USER_ID)

    # 1. Add trait
    stmt_add = "\u575a\u51b3\u62e5\u62b1\u53bb\u4e2d\u5fc3\u5316\u7f51\u7edc\u534f\u8bae\u4e0e\u67b6\u6784"
    res_add = client.post(
        "/api/dna/traits",
        json={
            "dimension": "viewpoint_stance",
            "statement": stmt_add,
            "user_id": uid,
        },
    )
    assert res_add.status_code == 200
    trait_data = res_add.json()
    trait_id = trait_data["id"]
    assert trait_data["status"] == "active"

    # 2. List traits
    res_list = client.get(f"/api/dna/traits?user_id={uid}&dimension=viewpoint_stance")
    assert res_list.status_code == 200
    traits = res_list.json()
    assert any(t["id"] == trait_id for t in traits)

    # 3. Update trait
    stmt_update = "\u575a\u5b9a\u63a8\u5d07\u53bb\u4e2d\u5fc3\u5316\u534f\u8bae\u4e0e\u81ea\u6258\u7ba1\u670d\u52a1"
    res_update = client.put(
        f"/api/dna/traits/{trait_id}",
        json={
            "statement": stmt_update,
            "confidence_score": 2.5,
            "user_id": uid,
        },
    )
    assert res_update.status_code == 200
    assert res_update.json()["statement"] == stmt_update
    assert res_update.json()["confidence_score"] == 2.5

    # 4. Toggle trait status to suppressed
    res_toggle = client.post(f"/api/dna/traits/{trait_id}/toggle?user_id={uid}")
    assert res_toggle.status_code == 200
    assert res_toggle.json()["status"] == "suppressed"

    # 5. Toggle trait status back to active
    res_toggle_back = client.post(
        "/api/dna/traits/toggle",
        json={"trait_id": trait_id, "user_id": uid, "enabled": True},
    )
    assert res_toggle_back.status_code == 200
    assert res_toggle_back.json()["status"] == "active"


def test_dna_export_and_import_json(session: Session, client: TestClient):
    uid = str(LOCAL_DEV_USER_ID)
    stmt_orig = "\u504f\u597d\u7b2c\u4e00\u6027\u539f\u7406\u4e0e\u5e95\u5c42\u5f52\u7eb3"
    CognitiveService.add_custom_trait(
        session=session,
        dimension=CognitiveDimension.VOCABULARY,
        statement=stmt_orig,
        user_id=uid,
    )

    # Export
    res_export = client.get(f"/api/dna/export?user_id={uid}")
    assert res_export.status_code == 200
    export_data = res_export.json()
    assert export_data["user_id"] == uid
    assert export_data["total_traits_count"] >= 1
    assert any(t["statement"] == stmt_orig for t in export_data["traits"])

    # Import in merge mode
    stmt_imported = "\u81ea\u9876\u5411\u4e0b\u5206\u5f62\u5c55\u5f00\u63a8\u5bfc"
    new_traits_payload = {
        "traits": [
            {
                "id": "imported_t1",
                "dimension": "logic_preference",
                "statement": stmt_imported,
                "confidence_score": 1.5,
                "status": "active",
            }
        ],
        "thinking_dna": {
            "vocabulary_habits": ["\u5de5\u7a0b\u843d\u5730\u89c6\u89d2"],
            "logic_preferences": ["\u56e0\u679c\u63a8\u5bfc"],
            "core_values": ["\u4e3b\u5f20: \u4e13\u6ce8\u5c0f\u800c\u7f8e\u9ad8\u73b0\u91d1\u6d41\u4e1a\u52a1"],
        },
        "mode": "merge",
        "user_id": uid,
    }
    res_import = client.post("/api/dna/import", json=new_traits_payload)
    assert res_import.status_code == 200
    imported_profile = res_import.json()
    statements = [t["statement"] for t in imported_profile["traits"]]
    assert stmt_imported in statements
    assert stmt_orig in statements

    # Import in overwrite mode
    stmt_only = "\u552f\u4e00\u51c6\u5219\uff1a\u8bda\u4fe1\u4ea4\u4ed8"
    overwrite_payload = {
        "traits": [
            {
                "id": "only_one",
                "dimension": "core_value",
                "statement": stmt_only,
                "confidence_score": 3.0,
                "status": "active",
            }
        ],
        "mode": "overwrite",
        "user_id": uid,
    }
    res_overwrite = client.post("/api/dna/import", json=overwrite_payload)
    assert res_overwrite.status_code == 200
    after_overwrite = res_overwrite.json()
    assert len(after_overwrite["traits"]) == 1
    assert after_overwrite["traits"][0]["statement"] == stmt_only

    # 4. Verify Export/Import Idempotency (confidence score must NOT inflate on roundtrip)
    res_export_pre = client.get(f"/api/dna/export?user_id={uid}")
    assert res_export_pre.status_code == 200
    export_pre_data = res_export_pre.json()
    initial_score = export_pre_data["traits"][0]["confidence_score"]

    # Re-import same export payload in merge mode
    res_reimport = client.post("/api/dna/import", json={**export_pre_data, "mode": "merge", "user_id": uid})
    assert res_reimport.status_code == 200

    res_export_post = client.get(f"/api/dna/export?user_id={uid}")
    assert res_export_post.status_code == 200
    post_score = res_export_post.json()["traits"][0]["confidence_score"]
    assert post_score == initial_score, f"Idempotency violation: score changed from {initial_score} to {post_score}"

    # 5. Verify import with missing id and dimension succeeds gracefully
    res_lenient_import = client.post(
        "/api/dna/import",
        json={
            "traits": [{"statement": "创作者必须掌握第一手信源"}],
            "mode": "merge",
            "user_id": uid,
        },
    )
    assert res_lenient_import.status_code == 200
    profile_data = res_lenient_import.json()
    added_trait = next((t for t in profile_data["traits"] if t["statement"] == "创作者必须掌握第一手信源"), None)
    assert added_trait is not None
    assert added_trait["dimension"] == "core_value"
    assert added_trait["id"] is not None


def test_viewpoint_conflict_detection(session: Session, client: TestClient):
    uid = str(LOCAL_DEV_USER_ID)

    # User profile has:
    # 1. \u5fc5\u987b\u575a\u5b9a\u652f\u6301\u53bb\u4e2d\u5fc3\u5316\u7f51\u7edc\u4e0e\u81ea\u6258\u7ba1\u534f\u8bae
    # 2. \u8f6f\u4ef6\u670d\u52a1\u5fc5\u987b\u575a\u6301\u957f\u671f\u4e3b\u4e49\u4e0e\u6536\u8d39\u53d8\u73b0
    CognitiveService.add_custom_trait(
        session=session,
        dimension=CognitiveDimension.VIEWPOINT_STANCE,
        statement="\u5fc5\u987b\u575a\u5b9a\u652f\u6301\u53bb\u4e2d\u5fc3\u5316\u7f51\u7edc\u4e0e\u81ea\u6258\u7ba1\u534f\u8bae",
        user_id=uid,
    )
    CognitiveService.add_custom_trait(
        session=session,
        dimension=CognitiveDimension.CORE_VALUE,
        statement="\u8f6f\u4ef6\u670d\u52a1\u5fc5\u987b\u575a\u6301\u957f\u671f\u4e3b\u4e49\u4e0e\u6536\u8d39\u53d8\u73b0",
        user_id=uid,
    )

    # 1. Test Conflict: Antonym pair (去中心化 vs 中心化)
    res_conflict1 = client.post(
        "/api/dna/conflicts/detect",
        json={
            "statement": "\u5728\u73b0\u4ee3\u57fa\u7840\u8bbe\u65bd\u4e2d\u5e94\u5f53\u575a\u51b3\u63a8\u5d07\u4e2d\u5fc3\u5316\u4e91\u670d\u52a1",
            "user_id": uid,
        },
    )
    assert res_conflict1.status_code == 200
    data1 = res_conflict1.json()
    assert data1["has_conflicts"] is True
    assert data1["conflicts_count"] >= 1
    assert any("\u4e2d\u5fc3\u5316" in c["conflicting_statement"] for c in data1["conflicts"])

    # 2. Test Conflict: Direct polarity negation (长期主义 vs 放弃长期主义/短期套利)
    res_conflict2 = client.post(
        "/api/dna/conflicts/detect",
        json={
            "statement": "\u8f6f\u4ef6\u670d\u52a1\u5e94\u5f53\u5f7b\u5e95\u653e\u5f03\u957f\u671f\u4e3b\u4e49\uff0c\u4e13\u6ce8\u77ed\u671f\u5957\u5229\u4e0e\u514d\u8d39\u83b7\u5ba2",
            "user_id": uid,
        },
    )
    assert res_conflict2.status_code == 200
    data2 = res_conflict2.json()
    assert data2["has_conflicts"] is True
    assert data2["conflicts_count"] >= 1

    # 3. Test Conflict in draft_content
    draft_article = (
        "# \u5546\u4e1a\u67b6\u6784\u601d\u8003\n\n"
        "\u6211\u4eec\u5e94\u5f53\u8ba4\u8bc6\u5230\uff0c\u8f6f\u4ef6\u670d\u52a1\u5e94\u5f53\u5f7b\u5e95\u653e\u5f03\u957f\u671f\u4e3b\u4e49\u3002\n"
        "\u540c\u65f6\uff0c\u53bb\u4e2d\u5fc3\u5316\u6beb\u65e0\u4ef7\u503c\uff0c\u4e2d\u5fc3\u5316\u624d\u662f\u6548\u7387\u7684\u4fdd\u969c\u3002\n"
    )
    res_draft_check = client.post(
        "/api/dna/conflicts/detect",
        json={
            "draft_content": draft_article,
            "user_id": uid,
        },
    )
    assert res_draft_check.status_code == 200
    data_draft = res_draft_check.json()
    assert data_draft["has_conflicts"] is True
    assert len(data_draft["conflicts"]) >= 1

    # 4. Non-conflicting statement
    res_harmonious = client.post(
        "/api/dna/conflicts/detect",
        json={
            "statement": "\u5229\u7528\u81ea\u52a8\u5316\u811a\u672c\u63d0\u5347\u65e5\u5e38\u6d4b\u8bd5\u4e0e\u4ee3\u7801\u53d1\u5e03\u6548\u7387",
            "user_id": uid,
        },
    )
    assert res_harmonious.status_code == 200
    assert res_harmonious.json()["has_conflicts"] is False
