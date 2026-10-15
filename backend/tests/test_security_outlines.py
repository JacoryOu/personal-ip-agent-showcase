"""Security regression tests for the outlines API surface.

Covers: credential-only identity, refusal of a foreign ``user_id``, and the
containment of engine/SDK error text behind the unified error contract.
"""

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.config import settings
from app.core.db import get_readonly_session, get_session
from app.engine.cognitive_engine import get_cognitive_engine
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


@pytest.fixture(name="local_client")
def local_client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session():
        yield session

    def override_get_readonly_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_readonly_session] = override_get_readonly_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_readonly_session, None)


@pytest.fixture(name="strict_client")
def strict_client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session():
        yield session

    def override_get_readonly_session():
        yield session

    old_local = settings.AUTH_LOCAL_DEV_MODE
    old_required = settings.AUTH_REQUIRED
    old_keys = settings.API_KEYS
    settings.AUTH_LOCAL_DEV_MODE = False
    settings.AUTH_REQUIRED = True
    settings.API_KEYS = "some-other-user=some-other-key"

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_readonly_session] = override_get_readonly_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_readonly_session, None)
        settings.AUTH_LOCAL_DEV_MODE = old_local
        settings.AUTH_REQUIRED = old_required
        settings.API_KEYS = old_keys


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


# --------------------------------------------------------------------------- #
# 1. Authentication required
# --------------------------------------------------------------------------- #

def test_outline_generate_requires_credentials(strict_client: TestClient):
    resp = strict_client.post("/api/outlines/generate", json={"topic": "t"})
    assert_error_contract(resp, 401, "AUTH_REQUIRED")


# --------------------------------------------------------------------------- #
# 2. Identity comes from the credential only
# --------------------------------------------------------------------------- #

def test_foreign_user_id_is_forbidden(local_client: TestClient):
    resp = local_client.post(
        "/api/outlines/generate",
        json={"topic": "t", "user_id": FOREIGN_USER_ID},
    )
    assert_error_contract(resp, 403, "FORBIDDEN")


def test_matching_user_id_is_accepted(local_client: TestClient, monkeypatch):
    """The compatibility field stays usable when it names the caller itself."""

    seen: dict = {}

    class OkEngine:
        async def explore_outlines(self, **kwargs):
            seen.update(kwargs)
            return {"outline_a": {}, "outline_b": {}}

    app.dependency_overrides[get_cognitive_engine] = lambda: OkEngine()
    try:
        resp = local_client.post(
            "/api/outlines/generate",
            json={"topic": "t", "user_id": LOCAL_USER_ID},
        )
    finally:
        app.dependency_overrides.pop(get_cognitive_engine, None)

    assert resp.status_code == 200, resp.text
    assert str(seen["user_id"]) == LOCAL_USER_ID


# --------------------------------------------------------------------------- #
# 3. Internal errors are collapsed, not echoed
# --------------------------------------------------------------------------- #

LEAKING = RuntimeError(
    "upstream failed: https://internal-host-01.corp.internal/v1/chat "
    "key=sk-live-SUPERSECRET-1234 file=C:\\Users\\admin\\vault\\private\\secrets.json"
)


def test_engine_errors_are_collapsed(local_client: TestClient):
    class FailingEngine:
        async def explore_outlines(self, **kwargs):
            raise LEAKING

    app.dependency_overrides[get_cognitive_engine] = lambda: FailingEngine()
    try:
        resp = local_client.post("/api/outlines/generate", json={"topic": "t"})
    finally:
        app.dependency_overrides.pop(get_cognitive_engine, None)

    assert_error_contract(resp, 500, "INTERNAL_ERROR")
    assert_no_internal_text(resp)


def test_value_error_is_reduced_to_a_public_validation_error(local_client: TestClient):
    class FailingEngine:
        async def explore_outlines(self, **kwargs):
            raise ValueError("sk-live-SUPERSECRET-1234 is not a valid key for this vault")

    app.dependency_overrides[get_cognitive_engine] = lambda: FailingEngine()
    try:
        resp = local_client.post("/api/outlines/generate", json={"topic": "t"})
    finally:
        app.dependency_overrides.pop(get_cognitive_engine, None)

    assert_error_contract(resp, 422, "VALIDATION_ERROR")
    assert_no_internal_text(resp)
