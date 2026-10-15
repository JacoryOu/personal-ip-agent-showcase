import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.api.outlines import get_outline_agent
from app.api.drafts import get_draft_agent
from app.schemas.outline_schemas import Outline, OutlineOutput, OutlineSection
from app.schemas.draft_schemas import DraftOutput


ROUTES_OWNER_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
ROUTES_OWNER_KEY = "routes-owner-key"
ROUTES_AUTH = {"X-API-Key": ROUTES_OWNER_KEY}


@pytest.fixture(autouse=True)
def routes_auth_settings():
    old_keys, old_local, old_required = settings.API_KEYS, settings.AUTH_LOCAL_DEV_MODE, settings.AUTH_REQUIRED
    settings.API_KEYS = f"{ROUTES_OWNER_ID}={ROUTES_OWNER_KEY}"
    settings.AUTH_LOCAL_DEV_MODE = False
    settings.AUTH_REQUIRED = True
    try:
        yield
    finally:
        settings.API_KEYS, settings.AUTH_LOCAL_DEV_MODE, settings.AUTH_REQUIRED = old_keys, old_local, old_required


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_outline():
    return {
        "title": "Outline 1",
        "rationale": "Rationale 1",
        "sections": [
            {
                "title": "Section 1",
                "bullet_points": ["Point 1", "Point 2"],
            }
        ],
    }


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Personal Cognitive IP Engine" in data["message"]


def test_generate_outlines_endpoint_success(client):
    mock_agent = MagicMock()
    mock_outlines = OutlineOutput(
        outline_a=Outline(
            title="Conventional Approach",
            rationale="Structured and analytical",
            sections=[OutlineSection(title="Intro", bullet_points=["A1"])],
        ),
        outline_b=Outline(
            title="Unconventional Approach",
            rationale="Contrarian and bold",
            sections=[OutlineSection(title="Hook", bullet_points=["B1"])],
        ),
    )
    mock_agent.generate_outlines = AsyncMock(return_value=mock_outlines)

    app.dependency_overrides[get_outline_agent] = lambda: mock_agent

    try:
        response = client.post(
            "/api/outlines/generate",
            headers=ROUTES_AUTH,
            json={"topic": "Micro-SaaS In 2026", "additional_context": "Focus on AI"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["outline_a"]["title"] == "Conventional Approach"
        assert data["outline_b"]["title"] == "Unconventional Approach"
        mock_agent.generate_outlines.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_outline_agent, None)


def test_generate_outlines_validation_error(client):
    response = client.post("/api/outlines/generate", headers=ROUTES_AUTH, json={"topic": "   "})
    assert response.status_code == 422


def test_generate_draft_endpoint_success(client, sample_outline):
    mock_agent = MagicMock()
    mock_draft = DraftOutput(
        title="Mastering Micro-SaaS",
        summary="A practical playbook for solo builders in 2026.",
        content="# Mastering Micro-SaaS\n\nContent here...",
        word_count=250,
    )
    mock_agent.generate_draft = AsyncMock(return_value=mock_draft)

    app.dependency_overrides[get_draft_agent] = lambda: mock_agent

    try:
        response = client.post(
            "/api/drafts/generate",
            headers=ROUTES_AUTH,
            json={
                "topic": "Micro-SaaS In 2026",
                "outline": sample_outline,
                "additional_context": "Direct, crisp style.",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Mastering Micro-SaaS"
        assert data["word_count"] == 250
        assert "# Mastering Micro-SaaS" in data["content"]
        mock_agent.generate_draft.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_draft_agent, None)


def test_generate_draft_validation_error(client):
    # Missing outline
    response = client.post("/api/drafts/generate", headers=ROUTES_AUTH, json={"topic": "Valid Topic"})
    assert response.status_code == 422


def test_generate_draft_error_handling(client, sample_outline):
    mock_agent = MagicMock()
    mock_agent.generate_draft = AsyncMock(side_effect=ValueError("Safety filter triggered"))

    app.dependency_overrides[get_draft_agent] = lambda: mock_agent

    try:
        response = client.post(
            "/api/drafts/generate",
            headers=ROUTES_AUTH,
            json={
                "topic": "Harmful Topic",
                "outline": sample_outline,
            },
        )
        assert response.status_code == 422
        body = response.json()
        # The upstream failure text must not be echoed back to the client.
        assert "Safety filter triggered" not in response.text
        assert body["detail"] == "The draft could not be generated from the provided input."
    finally:
        app.dependency_overrides.pop(get_draft_agent, None)
