import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.main import app
from app.core.db import get_session
from app.api.drafts import get_draft_agent
from app.engine.cognitive_engine import CognitiveEngine
from app.models.draft import Draft
from app.models.user import User
from app.schemas.draft_schemas import DraftOutput, ThinkingDNA
from app.schemas.outline_schemas import Outline, OutlineSection


OWNER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
OWNER_KEY = "archive-owner-key"
OTHER_KEY = "archive-other-key"
OWNER_AUTH = {"X-API-Key": OWNER_KEY}


@pytest.fixture(autouse=True)
def archive_auth_settings():
    old_keys, old_local, old_required = settings.API_KEYS, settings.AUTH_LOCAL_DEV_MODE, settings.AUTH_REQUIRED
    settings.API_KEYS = f"{OWNER_ID}={OWNER_KEY},{OTHER_ID}={OTHER_KEY}"
    settings.AUTH_LOCAL_DEV_MODE = False
    settings.AUTH_REQUIRED = True
    try:
        yield
    finally:
        settings.API_KEYS, settings.AUTH_LOCAL_DEV_MODE, settings.AUTH_REQUIRED = old_keys, old_local, old_required


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
            id=OWNER_ID,
            username="archive_tester",
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
async def test_generate_draft_autosaves_to_database(session: Session, client: TestClient):
    """Verifies POST /api/drafts/generate automatically persists the draft into database archive."""
    mock_agent = MagicMock()
    mock_draft = DraftOutput(
        title="AI Native Workflows",
        summary="A guide to modern AI engineering",
        content="# AI Native Workflows\n\nHere is the full text.",
        word_count=350,
    )
    mock_agent.generate_draft = AsyncMock(return_value=mock_draft)
    app.dependency_overrides[get_draft_agent] = lambda: mock_agent

    try:
        user_id = str(OWNER_ID)
        res = client.post(
            "/api/drafts/generate",
            headers=OWNER_AUTH,
            json={
                "topic": "AI Native Engineering",
                "outline": {
                    "title": "Structure A",
                    "rationale": "Clear and fast",
                    "sections": [{"title": "Introduction", "bullet_points": ["Point 1"]}],
                },
                "user_id": user_id,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "AI Native Workflows"
        assert data["id"] is not None
        saved_id = uuid.UUID(data["id"])

        # Check in DB
        db_draft = session.get(Draft, saved_id)
        assert db_draft is not None
        assert db_draft.topic == "AI Native Engineering"
        assert db_draft.original_ai_draft == "# AI Native Workflows\n\nHere is the full text."
        assert db_draft.metadata_.get("title") == "AI Native Workflows"
        assert db_draft.metadata_.get("word_count") == 350
    finally:
        app.dependency_overrides.pop(get_draft_agent, None)


def test_list_drafts_and_filters(session: Session, client: TestClient):
    """Verifies GET /api/drafts lists archives and filters by topic, keyword, and user_id."""
    uid = OWNER_ID
    other_uid = OTHER_ID
    user2 = User(id=other_uid, username="other_user")
    session.add(user2)

    draft1 = Draft(
        user_id=uid,
        topic="Python Web Frameworks",
        original_ai_draft="FastAPI and Django analysis",
        metadata_={"title": "FastAPI Playbook", "summary": "FastAPI is great"},
    )
    draft2 = Draft(
        user_id=uid,
        topic="Solopreneur Playbook",
        original_ai_draft="How to build indie software",
        metadata_={"title": "Indie Hacker Guide"},
    )
    draft3 = Draft(
        user_id=other_uid,
        topic="Rust Systems",
        original_ai_draft="Memory safety and concurrency",
        metadata_={"title": "Rust Primer"},
    )
    session.add_all([draft1, draft2, draft3])
    session.commit()

    # List all
    res = client.get("/api/drafts", headers=OWNER_AUTH)
    assert res.status_code == 200
    all_drafts = res.json()
    # Ownership scoping: the caller only sees their own drafts.
    assert len(all_drafts) == 2
    assert {d["user_id"] for d in all_drafts} == {str(uid)}

    # Filter by user_id
    res_user = client.get(f"/api/drafts?user_id={uid}", headers=OWNER_AUTH)
    assert res_user.status_code == 200
    user_drafts = res_user.json()
    assert len(user_drafts) == 2

    # A client-supplied user_id can never widen the visible scope.
    # Conflicting user_id is rejected outright rather than silently honoured.
    res_other = client.get(f"/api/drafts?user_id={other_uid}", headers=OWNER_AUTH)
    assert res_other.status_code == 403

    # Filter by topic
    res_topic = client.get("/api/drafts?topic=Python", headers=OWNER_AUTH)
    assert res_topic.status_code == 200
    topic_drafts = res_topic.json()
    assert len(topic_drafts) == 1
    assert topic_drafts[0]["title"] == "FastAPI Playbook"

    # Filter by keyword (matches content)
    # keyword filter is also owner-scoped: the other user's draft stays hidden.
    res_kw = client.get("/api/drafts?keyword=concurrency", headers=OWNER_AUTH)
    assert res_kw.status_code == 200
    assert len(res_kw.json()) == 0


def test_get_update_and_delete_draft(session: Session, client: TestClient):
    """Verifies GET, PUT, and DELETE operations for a draft archive."""
    uid = OWNER_ID
    draft = Draft(
        user_id=uid,
        topic="Draft Lifecycle Test",
        original_ai_draft="Initial draft generated by AI",
        metadata_={"title": "Lifecycle Initial Title"},
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)

    # 1. GET by ID
    res = client.get(f"/api/drafts/{draft.id}", headers=OWNER_AUTH)
    assert res.status_code == 200
    assert res.json()["topic"] == "Draft Lifecycle Test"
    assert res.json()["title"] == "Lifecycle Initial Title"

    # 2. PUT Update user_final_draft and title
    res_update = client.put(
        f"/api/drafts/{draft.id}",
        headers=OWNER_AUTH,
        json={
            "title": "Lifecycle Revised Title",
            "user_final_draft": "Revised text by author with personal voice.",
        },
    )
    assert res_update.status_code == 200
    updated_data = res_update.json()
    assert updated_data["title"] == "Lifecycle Revised Title"
    assert updated_data["user_final_draft"] == "Revised text by author with personal voice."
    assert updated_data["content"] == "Revised text by author with personal voice."
    assert updated_data["word_count"] == len("Revised text by author with personal voice.")

    # 3. DELETE
    res_delete = client.delete(f"/api/drafts/{draft.id}", headers=OWNER_AUTH)
    assert res_delete.status_code == 200
    assert res_delete.json()["success"] is True

    # 4. Verify 404 after deletion
    res_get_deleted = client.get(f"/api/drafts/{draft.id}", headers=OWNER_AUTH)
    assert res_get_deleted.status_code == 404


def test_draft_delete_with_associated_dna_records_is_fk_safe(session: Session, client: TestClient):
    """Verifies that deleting a draft with associated DNARecords safely nullifies references
    without triggering foreign key constraint violations.
    """
    from app.models.dna_record import DNARecord
    uid = OWNER_ID

    # 1. Create draft
    draft = Draft(
        user_id=uid,
        topic="Architecture Refactoring",
        original_ai_draft="Original AI content",
        metadata_={"title": "Refactoring Post"},
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)

    # 2. Create DNA record referencing draft
    dna_record = DNARecord(
        user_id=uid,
        draft_id=draft.id,
        dna_data={"vocabulary_habits": ["重构", "解耦"]},
    )
    session.add(dna_record)
    session.commit()
    session.refresh(dna_record)

    # 3. Delete draft via API
    res_del = client.delete(f"/api/drafts/{draft.id}", headers=OWNER_AUTH)
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # 4. Draft is deleted
    assert session.get(Draft, draft.id) is None

    # 5. DNA record is preserved with draft_id cleared
    session.refresh(dna_record)
    assert dna_record.id is not None
    assert dna_record.draft_id is None
