"""Security regression tests for the viral analysis API surface.

Covers: credential-only identity, refusal of a foreign ``user_id``, ownership
of a persisted analysis, and containment of service/SDK error text.
"""

import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.config import settings
from app.core.db import get_session
from app.main import app

LOCAL_USER_ID = "00000000-0000-0000-0000-000000000001"
FOREIGN_USER_ID = "00000000-0000-0000-0000-0000000000ff"

SECRETS = (
    r"C:\Users\admin\vault\private\secrets.json",
    "https://internal-host-01.corp.internal/v1/chat",
    "sk-live-SUPERSECRET-1234",
    "Traceback (most recent call last)",
    "sqlite:////srv/app/data/private.db",
)


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    import app.models  # noqa: F401  (populate SQLModel metadata)

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as sess:
        yield sess


def _client(session: Session, strict: bool) -> Generator[TestClient, None, None]:
    def override_get_session():
        yield session

    old_local = settings.AUTH_LOCAL_DEV_MODE
    old_required = settings.AUTH_REQUIRED
    old_keys = settings.API_KEYS
    if strict:
        settings.AUTH_LOCAL_DEV_MODE = False
        settings.AUTH_REQUIRED = True
        settings.API_KEYS = "some-other-user=some-other-key"

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        settings.AUTH_LOCAL_DEV_MODE = old_local
        settings.AUTH_REQUIRED = old_required
        settings.API_KEYS = old_keys


@pytest.fixture(name="local_client")
def local_client_fixture(session: Session) -> Generator[TestClient, None, None]:
    yield from _client(session, strict=False)


@pytest.fixture(name="strict_client")
def strict_client_fixture(session: Session) -> Generator[TestClient, None, None]:
    yield from _client(session, strict=True)


def assert_error_contract(response, status_code: int, code: str) -> dict:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["error"]["code"] == code, body
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    header_request_id = response.headers.get("X-Request-ID")
    assert header_request_id
    assert body["error"]["request_id"] == header_request_id
    return body


def assert_no_internal_text(response) -> None:
    raw = response.text
    for needle in SECRETS:
        assert needle not in raw, f"internal text leaked: {needle!r} in {raw[:400]!r}"
    assert "Traceback" not in raw


def _record(owner: str) -> "object":
    from app.models.viral_analysis import ViralSemanticAnalysisRecord

    record = ViralSemanticAnalysisRecord(
        id=uuid.uuid4(),
        user_id=uuid.UUID(owner),
        source_title="t",
        source_content_hash="h",
        source_platform="wechat",
        analysis_data={},
        warnings=[],
    )
    return record


# --------------------------------------------------------------------------- #
# 1. Authentication required
# --------------------------------------------------------------------------- #

def test_analyze_requires_credentials(strict_client: TestClient):
    resp = strict_client.post("/api/viral-analysis/analyze", json={"content": "body"})
    assert_error_contract(resp, 401, "AUTH_REQUIRED")


def test_get_analysis_requires_credentials(strict_client: TestClient):
    resp = strict_client.get(f"/api/viral-analysis/{uuid.uuid4()}")
    assert_error_contract(resp, 401, "AUTH_REQUIRED")


# --------------------------------------------------------------------------- #
# 2. Identity comes from the credential only
# --------------------------------------------------------------------------- #

def test_foreign_user_id_in_body_is_forbidden(local_client: TestClient):
    resp = local_client.post(
        "/api/viral-analysis/analyze",
        json={"content": "body", "user_id": FOREIGN_USER_ID},
    )
    assert_error_contract(resp, 403, "FORBIDDEN")


def test_matching_user_id_is_passed_through(local_client: TestClient, monkeypatch):
    seen: dict = {}

    class OkService:
        async def analyze_article(self, **kwargs):
            seen.update(kwargs)
            return {"id": str(uuid.uuid4()), "status": "completed", "extraction_mode": "llm", "source_title": "t", "analysis": {}, "warnings": []}

    from app.api import viral_analysis as viral_api

    monkeypatch.setattr(viral_api, "ViralSemanticService", OkService)

    resp = local_client.post(
        "/api/viral-analysis/analyze",
        json={"content": "body", "user_id": LOCAL_USER_ID},
    )

    assert resp.status_code == 200, resp.text
    assert str(seen["user_id"]) == LOCAL_USER_ID


# --------------------------------------------------------------------------- #
# 3. Ownership of a persisted analysis
# --------------------------------------------------------------------------- #

def test_get_foreign_analysis_is_forbidden(local_client: TestClient, session: Session):
    record = _record(FOREIGN_USER_ID)
    session.add(record)
    session.commit()

    resp = local_client.get(f"/api/viral-analysis/{record.id}")
    assert_error_contract(resp, 403, "FORBIDDEN")


def test_get_unknown_analysis_is_not_found(local_client: TestClient):
    resp = local_client.get(f"/api/viral-analysis/{uuid.uuid4()}")
    assert_error_contract(resp, 404, "NOT_FOUND")


def test_get_own_analysis_is_allowed(local_client: TestClient, session: Session, monkeypatch):
    record = _record(LOCAL_USER_ID)
    session.add(record)
    session.commit()

    class OkService:
        def get_analysis(self, analysis_id, sess):
            return {
                "id": str(analysis_id),
                "status": "completed",
                "extraction_mode": "llm",
                "source_title": "t",
                "analysis": {},
                "warnings": [],
            }

    from app.api import viral_analysis as viral_api

    monkeypatch.setattr(viral_api, "ViralSemanticService", OkService)

    resp = local_client.get(f"/api/viral-analysis/{record.id}")
    assert resp.status_code == 200, resp.text


# --------------------------------------------------------------------------- #
# 4. Internal errors are collapsed, not echoed
# --------------------------------------------------------------------------- #

LEAKING = RuntimeError(
    "upstream failed: https://internal-host-01.corp.internal/v1/chat "
    "key=sk-live-SUPERSECRET-1234 file=C:\\Users\\admin\\vault\\private\\secrets.json"
)


def test_service_errors_are_collapsed(local_client: TestClient, monkeypatch):
    class FailingService:
        async def analyze_article(self, **kwargs):
            raise LEAKING

    from app.api import viral_analysis as viral_api

    monkeypatch.setattr(viral_api, "ViralSemanticService", FailingService)

    resp = local_client.post("/api/viral-analysis/analyze", json={"content": "body"})

    assert_error_contract(resp, 500, "INTERNAL_ERROR")
    assert_no_internal_text(resp)


def test_value_error_is_reduced_to_a_public_validation_error(
    local_client: TestClient, monkeypatch
):
    class FailingService:
        async def analyze_article(self, **kwargs):
            raise ValueError("sk-live-SUPERSECRET-1234 is not a valid key for this vault")

    from app.api import viral_analysis as viral_api

    monkeypatch.setattr(viral_api, "ViralSemanticService", FailingService)

    resp = local_client.post("/api/viral-analysis/analyze", json={"content": "body"})

    assert_error_contract(resp, 422, "VALIDATION_ERROR")
    assert_no_internal_text(resp)
