"""Security regression tests for the DNA API surface.

Covers the guarantees required by the second security batch:

* the credential is the only identity source (no anonymous access to private
  DNA routes, and a foreign ``user_id`` is refused);
* resource ownership is enforced on drafts and on record listings;
* raw exception text (absolute paths, internal URLs, secrets, tracebacks)
  never reaches the client;
* every error response carries ``error.code`` and a ``request_id`` that matches
  the ``X-Request-ID`` header.
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


@pytest.fixture(name="strict_client")
def strict_client_fixture(
    session: Session,
) -> Generator[TestClient, None, None]:
    """A client with authentication *required* (no local-dev fallback)."""

    def override_get_session():
        yield session

    old_local = settings.AUTH_LOCAL_DEV_MODE
    old_required = settings.AUTH_REQUIRED
    old_keys = settings.API_KEYS
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
def local_client_fixture(
    session: Session,
) -> Generator[TestClient, None, None]:
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


def assert_error_contract(response, status_code: int, code: str) -> dict:
    """Assert the unified error contract and return the parsed body."""
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["error"]["code"] == code, body
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    # The body id must be quotable back to the operator via the header.
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
# 1. Authentication is required on private DNA routes
# --------------------------------------------------------------------------- #

PRIVATE_ROUTES = [
    ("post", "/api/dna/extract", {"original_ai_draft": "a", "user_final_draft": "b"}),
    ("post", "/api/dna/ingest-own-work", {"content": "hello"}),
    ("post", "/api/dna/deconstruct-benchmark", {"content": "hello"}),
    ("post", "/api/dna/dialogue-clash", {"messages": [{"role": "user", "content": "hello"}]}),
    ("get", "/api/dna/profile", None),
    ("get", "/api/dna/records", None),
    ("get", "/api/dna/traits", None),
    ("get", "/api/dna/benchmarks", None),
    ("get", "/api/dna/export", None),
    ("post", "/api/dna/traits/pin", {"trait_id": "x"}),
    ("post", "/api/dna/traits/unpin", {"trait_id": "x"}),
    ("post", "/api/dna/traits/suppress", {"trait_id": "x"}),
    ("post", "/api/dna/traits/toggle", {"trait_id": "x", "enabled": True}),
    ("post", "/api/dna/detect-conflicts", {}),
]


@pytest.mark.parametrize("method,path,payload", PRIVATE_ROUTES)
def test_private_dna_routes_require_credentials(
    strict_client: TestClient, method, path, payload
):
    if method == "get":
        resp = strict_client.get(path)
    else:
        resp = strict_client.post(path, json=payload)
    assert_error_contract(resp, 401, "AUTH_REQUIRED")


def test_skills_route_requires_authentication(strict_client: TestClient):
    """``/api/dna/skills`` is mounted on the private aggregate router.

    It used to stay anonymous; the default-private router boundary now
    requires an authenticated identity like every other business endpoint.
    """
    resp = strict_client.get("/api/dna/skills")
    assert resp.status_code == 401, resp.text


# --------------------------------------------------------------------------- #
# 2. A client-supplied user_id is never an identity source
# --------------------------------------------------------------------------- #

FOREIGN_BODY_ROUTES = [
    ("post", "/api/dna/extract", {"original_ai_draft": "a", "user_final_draft": "b"}),
    ("post", "/api/dna/ingest-own-work", {"content": "hello"}),
    ("post", "/api/dna/deconstruct-benchmark", {"content": "hello"}),
    ("post", "/api/dna/dialogue-clash", {"messages": [{"role": "user", "content": "hello"}]}),
    ("post", "/api/dna/detect-conflicts", {}),
]


@pytest.mark.parametrize("method,path,payload", FOREIGN_BODY_ROUTES)
def test_foreign_user_id_in_body_is_forbidden(
    local_client: TestClient, method, path, payload
):
    body = dict(payload)
    body["user_id"] = FOREIGN_USER_ID
    resp = local_client.post(path, json=body)
    assert_error_contract(resp, 403, "FORBIDDEN")


@pytest.mark.parametrize(
    "path",
    [
        "/api/dna/profile?user_id=" + FOREIGN_USER_ID,
        "/api/dna/traits?user_id=" + FOREIGN_USER_ID,
        "/api/dna/benchmarks?user_id=" + FOREIGN_USER_ID,
        "/api/dna/export?user_id=" + FOREIGN_USER_ID,
    ],
)
def test_foreign_user_id_in_query_is_forbidden(local_client: TestClient, path: str):
    resp = local_client.get(path)
    assert_error_contract(resp, 403, "FORBIDDEN")


# --------------------------------------------------------------------------- #
# 3. Resource ownership
# --------------------------------------------------------------------------- #

def test_extract_rejects_a_draft_owned_by_someone_else(
    local_client: TestClient, session: Session
):
    from app.models.draft import Draft

    foreign_draft = Draft(
        id=uuid.uuid4(),
        user_id=uuid.UUID(FOREIGN_USER_ID),
        topic="t",
        original_ai_draft="a",
    )
    session.add(foreign_draft)
    session.commit()

    resp = local_client.post(
        "/api/dna/extract",
        json={"draft_id": str(foreign_draft.id)},
    )
    assert_error_contract(resp, 403, "FORBIDDEN")


def test_extract_reports_unknown_draft_as_not_found(local_client: TestClient):
    resp = local_client.post("/api/dna/extract", json={"draft_id": str(uuid.uuid4())})
    assert_error_contract(resp, 404, "NOT_FOUND")


def test_records_listing_is_scoped_to_the_authenticated_user(
    local_client: TestClient, session: Session
):
    from app.models.dna_record import DNARecord

    mine = DNARecord(
        id=uuid.uuid4(),
        user_id=uuid.UUID(LOCAL_USER_ID),
        dna_data={"marker": "mine"},
    )
    theirs = DNARecord(
        id=uuid.uuid4(),
        user_id=uuid.UUID(FOREIGN_USER_ID),
        dna_data={"marker": "theirs"},
    )
    session.add(mine)
    session.add(theirs)
    session.commit()

    resp = local_client.get("/api/dna/records")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert rows, "the caller's own record should be returned"
    assert all(row["user_id"] == LOCAL_USER_ID for row in rows)
    assert "theirs" not in resp.text


# --------------------------------------------------------------------------- #
# 4. Internal errors are collapsed, not echoed
# --------------------------------------------------------------------------- #

LEAKING = RuntimeError(
    "upstream failed: https://internal-host-01.corp.internal/v1/chat "
    "key=sk-live-SUPERSECRET-1234 file=C:\\Users\\admin\\vault\\private\\secrets.json"
)


def test_ingest_own_work_does_not_echo_engine_errors(local_client: TestClient, monkeypatch):
    from app.engine.cognitive_engine import CognitiveEngine

    def boom(self, *args, **kwargs):
        raise LEAKING

    monkeypatch.setattr(CognitiveEngine, "ingest_own_works_for_dna", boom)

    resp = local_client.post("/api/dna/ingest-own-work", json={"content": "hello"})

    assert_error_contract(resp, 500, "INTERNAL_ERROR")
    assert_no_internal_text(resp)


def test_extract_does_not_echo_engine_errors(local_client: TestClient, monkeypatch):
    from app.engine.cognitive_engine import CognitiveEngine

    async def boom(self, *args, **kwargs):
        raise LEAKING

    monkeypatch.setattr(CognitiveEngine, "evolve_with_diff", boom)

    resp = local_client.post(
        "/api/dna/extract",
        json={"original_ai_draft": "a", "user_final_draft": "b"},
    )

    assert_error_contract(resp, 500, "INTERNAL_ERROR")
    assert_no_internal_text(resp)


def test_value_error_is_reduced_to_a_public_validation_error(
    local_client: TestClient, monkeypatch
):
    from app.engine.cognitive_engine import CognitiveEngine

    def boom(self, *args, **kwargs):
        raise ValueError("sk-live-SUPERSECRET-1234 is not a valid key for this vault")

    monkeypatch.setattr(CognitiveEngine, "ingest_own_works_for_dna", boom)

    resp = local_client.post("/api/dna/ingest-own-work", json={"content": "hello"})

    assert_error_contract(resp, 422, "VALIDATION_ERROR")
    assert_no_internal_text(resp)
