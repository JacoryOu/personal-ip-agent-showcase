import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.auth import LOCAL_DEV_USER_ID
from app.core.db import get_session
from app.api.dna import get_diff_agent
from app.models.draft import Draft
from app.models.user import User
from app.models.dna_record import DNARecord
from app.schemas.diff_schemas import DNAExtractionOutput, ThinkingDNA


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Create a test user
        user = User(id=LOCAL_DEV_USER_ID, username="test_author", email="author@example.com")
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


def test_extract_dna_zero_diff(client: TestClient):
    """
    Test zero-diff early return via API.
    """
    mock_agent = MagicMock()
    mock_agent.extract_dna = AsyncMock(
        return_value=DNAExtractionOutput(
            has_diff=False,
            diff_summary="No modifications detected between drafts.",
            thinking_dna=ThinkingDNA(
                vocabulary_habits=[],
                logic_preferences=[],
                core_values=[],
                summary="Drafts are identical; no cognitive delta to extract.",
            ),
        )
    )

    app.dependency_overrides[get_diff_agent] = lambda: mock_agent

    try:
        response = client.post(
            "/api/dna/extract",
            json={
                "original_ai_draft": "Identical content here.",
                "user_final_draft": "Identical content here.",
                "topic": "Zero Diff Test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_diff"] is False
        assert data["dna_record_id"] is None
        assert "No modifications" in data["diff_summary"]
        mock_agent.extract_dna.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_diff_agent, None)


def test_extract_dna_with_modifications_persists_to_db(client: TestClient, session: Session):
    """
    Test successful extraction with modifications, verifying persistence in DNARecord.
    """
    mock_agent = MagicMock()
    mock_agent.extract_dna = AsyncMock(
        return_value=DNAExtractionOutput(
            has_diff=True,
            diff_summary="Replaced corporate fluff with concrete code examples.",
            thinking_dna=ThinkingDNA(
                vocabulary_habits=["Prefers code idioms over metaphors", "Short declarative sentences"],
                logic_preferences=["Bottom-up induction from code to architecture"],
                core_values=["Developer ergonomics", "Ruthless pragmatism"],
                summary="Craftsman-centric builder style prioritizing concrete artifacts.",
            ),
        )
    )

    app.dependency_overrides[get_diff_agent] = lambda: mock_agent

    try:
        response = client.post(
            "/api/dna/extract",
            json={
                "original_ai_draft": "In today's landscape, software architectures can be viewed as tapestry.",
                "user_final_draft": "Let's inspect the code directly. Here is how memory is allocated.",
                "topic": "Software Craftsmanship",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_diff"] is True
        assert data["dna_record_id"] is not None
        assert len(data["thinking_dna"]["vocabulary_habits"]) == 2
        assert "Ruthless pragmatism" in data["thinking_dna"]["core_values"]

        # Verify persisted in database
        saved_record = session.get(DNARecord, uuid.UUID(data["dna_record_id"]))
        assert saved_record is not None
        assert "Developer ergonomics" in saved_record.dna_data["core_values"]
        assert data["draft_id"] is not None
        saved_draft = session.get(Draft, uuid.UUID(data["draft_id"]))
        assert saved_draft is not None
        assert saved_draft.user_final_draft == "Let's inspect the code directly. Here is how memory is allocated."
    finally:
        app.dependency_overrides.pop(get_diff_agent, None)


def test_extract_dna_with_draft_id_association(client: TestClient, session: Session):
    """
    Test extracting DNA for an existing Draft in DB, verifying that Draft.user_final_draft is updated.
    """
    user = session.exec(select(User)).first()
    draft = Draft(
        user_id=user.id,
        topic="Micro-SaaS In 2026",
        original_ai_draft="Original AI content for Micro-SaaS.",
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)

    mock_agent = MagicMock()
    mock_agent.extract_dna = AsyncMock(
        return_value=DNAExtractionOutput(
            has_diff=True,
            diff_summary="Added personal bootstrap revenue numbers.",
            thinking_dna=ThinkingDNA(
                vocabulary_habits=["MRR", "Churn"],
                logic_preferences=["Metrics-first"],
                core_values=["Financial independence"],
                summary="Solo founder perspective.",
            ),
            draft_id=draft.id,
        )
    )

    app.dependency_overrides[get_diff_agent] = lambda: mock_agent

    try:
        response = client.post(
            "/api/dna/extract",
            json={
                "draft_id": str(draft.id),
                "original_ai_draft": draft.original_ai_draft,
                "user_final_draft": "My actual MRR reached $12k this month with zero paid ads.",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_diff"] is True
        assert data["draft_id"] == str(draft.id)
        assert data["dna_record_id"] is not None

        # Verify draft was updated in DB
        session.refresh(draft)
        assert draft.user_final_draft == "My actual MRR reached $12k this month with zero paid ads."
    finally:
        app.dependency_overrides.pop(get_diff_agent, None)


def test_extract_dna_draft_not_found(client: TestClient):
    fake_id = uuid.uuid4()
    response = client.post(
        "/api/dna/extract",
        json={
            "draft_id": str(fake_id),
            "original_ai_draft": "Some text",
            "user_final_draft": "Changed text",
        },
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    # The public contract must not echo the internal resource identifier.
    assert str(fake_id) not in json.dumps(body)
    assert response.headers["X-Request-ID"] == body["error"]["request_id"]


def test_extract_dna_validation_error(client: TestClient):
    # Empty payloads
    response = client.post(
        "/api/dna/extract",
        json={"original_ai_draft": "", "user_final_draft": ""},
    )
    assert response.status_code == 422


def test_list_dna_records(client: TestClient, session: Session):
    user = session.exec(select(User)).first()
    record = DNARecord(
        user_id=user.id,
        dna_data={"vocabulary_habits": ["brevity"], "core_values": ["clarity"]},
    )
    session.add(record)
    session.commit()

    response = client.get("/api/dna/records")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["dna_data"]["vocabulary_habits"] == ["brevity"]
