# -*- coding: utf-8 -*-
"""Security regression tests for the drafts / blueprints / platforms API.

Scope of this file:

1. No raw exception text (SDK payloads, DB messages, filesystem paths,
   tracebacks) may appear in a response body.
2. Every error body uses the unified ``error.code`` + ``error.request_id``
   contract, and that request id matches the ``X-Request-ID`` header.
3. Routes that address user-private resources derive identity from the
   presented credential only, and reject cross-user access.
"""

from __future__ import annotations

import uuid
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.auth import AuthenticatedUser
from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.models.user import User

OWNER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
OTHER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
OWNER_KEY = "sec2-owner-key"
OTHER_KEY = "sec2-other-key"

# Text that must never survive into a response body.
SECRET_MARKERS = (
    "Traceback (most recent call last)",
    "sqlite3.",
    "sqlalchemy.exc",
    "openai",
    "Incorrect API key provided",
    ".venv\\Lib\\site-packages",
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture(autouse=True)
def auth_settings():
    old_keys, old_local, old_required = settings.API_KEYS, settings.AUTH_LOCAL_DEV_MODE, settings.AUTH_REQUIRED
    settings.API_KEYS = f"{OWNER_ID}={OWNER_KEY},{OTHER_ID}={OTHER_KEY}"
    settings.AUTH_LOCAL_DEV_MODE = False
    settings.AUTH_REQUIRED = True
    try:
        yield
    finally:
        settings.API_KEYS, settings.AUTH_LOCAL_DEV_MODE, settings.AUTH_REQUIRED = old_keys, old_local, old_required


@pytest.fixture(name="test_engine")
def _engine():
    import app.models  # noqa: F401

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(test_engine: Session) -> Session:
    with Session(test_engine) as sess:
        for uid, name in ((OWNER_ID, "sec2-owner"), (OTHER_ID, "sec2-other")):
            if not sess.get(User, uid):
                sess.add(User(id=uid, username=name))
        sess.commit()
        yield sess


@pytest.fixture
def client(session: Session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def owner_headers():
    return {"Authorization": f"Bearer {OWNER_KEY}"}


@pytest.fixture
def other_headers():
    return {"Authorization": f"Bearer {OTHER_KEY}"}


# ==============================================================================
# Helpers
# ==============================================================================

def assert_error_envelope(resp, expected_code: str, expected_status: int) -> dict:
    """Assert the unified error contract and that no internal text leaked."""
    assert resp.status_code == expected_status, resp.text
    body = resp.json()

    assert "error" in body, body
    assert body["error"]["code"] == expected_code, body
    assert body["error"]["message"], body

    # The request id in the body must match the response header, so a client can
    # quote one id that also appears in the server log.
    header_rid = resp.headers.get("X-Request-ID")
    assert header_rid, resp.headers
    assert body["error"]["request_id"] == header_rid, body

    flat = resp.text
    for marker in SECRET_MARKERS:
        assert marker not in flat, f"internal detail leaked ({marker!r}): {flat}"
    return body


def seed_draft(session: Session, owner: uuid.UUID, topic: str = "sec draft") -> str:
    from app.models.draft import Draft

    draft = Draft(
        id=uuid.uuid4(),
        user_id=owner,
        topic=topic,
        original_ai_draft="ai text",
        user_final_draft="user text",
        metadata_={},
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return str(draft.id)


# ==============================================================================
# drafts: no raw exception leakage
# ==============================================================================

def test_draft_internal_error_is_not_echoed(session, client, owner_headers):
    """A DB failure must collapse to a fixed INTERNAL_ERROR body, logged only."""
    boom = "SELECT * FROM secret_table failed: /srv/private/path.db is unreadable"
    draft_id = seed_draft(session, OWNER_ID)

    class BoomSession:
        def __getattr__(self, name):
            def _raise(*args, **kwargs):
                raise RuntimeError(boom)
            return _raise

    app.dependency_overrides[get_session] = lambda: BoomSession()
    try:
        resp = client.put(
            f"/api/drafts/{draft_id}",
            json={"topic": "new topic"},
            headers=owner_headers,
        )
    finally:
        def override_get_session():
            yield session
        app.dependency_overrides[get_session] = override_get_session

    body = assert_error_envelope(resp, "INTERNAL_ERROR", 500)
    assert body["error"]["message"] == "Internal server error."
    assert boom not in resp.text
    assert "secret_table" not in resp.text


def test_blueprint_value_error_is_not_echoed(client, owner_headers, monkeypatch):
    from app.api import blueprints as bp_api

    leak = "could not fetch https://internal-host.corp/secret-doc: token sk-live-DO-NOT-LEAK"

    async def boom(*args, **kwargs):
        raise ValueError(leak)

    monkeypatch.setattr(bp_api.CognitiveEngine, "extract_blueprint_from_text", boom)

    resp = client.post(
        "/api/blueprints/extract",
        json={"content": "some article"},
        headers=owner_headers,
    )
    assert_error_envelope(resp, "VALIDATION_ERROR", 422)
    assert "sk-live-DO-NOT-LEAK" not in resp.text
    assert "internal-host.corp" not in resp.text


def test_blueprint_empty_input_is_a_public_validation_error(client, owner_headers):
    resp = client.post("/api/blueprints/extract", json={}, headers=owner_headers)
    assert_error_envelope(resp, "VALIDATION_ERROR", 422)


def test_platform_value_error_is_not_echoed(session, client, owner_headers, monkeypatch):
    from app.api import platforms as platforms_api
    from app.models.benchmark_account import BenchmarkAccount

    acct = BenchmarkAccount(
        user_id=OWNER_ID,
        platform="wechat",
        account_name="sec-acct",
        account_id="sec-acct",
    )
    session.add(acct)
    session.commit()
    session.refresh(acct)

    leak = "no such account in table benchmark_account (host db-03.corp:5432)"

    def boom(*args, **kwargs):
        raise ValueError(leak)

    # Patch the exact service entry point that platforms.py calls, so the raise
    # happens inside the route's own ``except ValueError`` block.
    monkeypatch.setattr(
        platforms_api.PlatformCrawlerService,
        "fetch_account_posts",
        staticmethod(boom),
    )

    resp = client.get(f"/api/platforms/accounts/{acct.id}/feed", headers=owner_headers)
    assert_error_envelope(resp, "NOT_FOUND", 404)
    assert "db-03.corp" not in resp.text


def test_platform_qr_session_error_is_public(client, owner_headers):
    resp = client.post(
        "/api/platforms/credentials/qr/simulate-confirm",
        json={"session_key": "does-not-exist"},
        headers=owner_headers,
    )
    assert_error_envelope(resp, "NOT_FOUND", 404)


# ==============================================================================
# drafts: trusted identity + ownership
# ==============================================================================

def test_draft_routes_require_credentials(session, client):
    draft_id = seed_draft(session, OWNER_ID)
    for resp in (
        client.get("/api/drafts/"),
        client.get(f"/api/drafts/{draft_id}"),
        client.put(f"/api/drafts/{draft_id}", json={"topic": "x"}),
        client.delete(f"/api/drafts/{draft_id}"),
        client.get(f"/api/drafts/{draft_id}/feedback"),
    ):
        assert resp.status_code == 401, resp.text
        assert resp.json()["error"]["code"] == "AUTH_REQUIRED"


def test_draft_list_only_returns_caller_drafts(session, client, owner_headers):
    mine = seed_draft(session, OWNER_ID, "mine")
    seed_draft(session, OTHER_ID, "theirs")

    ids = {d["id"] for d in client.get("/api/drafts/", headers=owner_headers).json()}
    assert mine in ids
    assert all(d["user_id"] == str(OWNER_ID) for d in client.get("/api/drafts/", headers=owner_headers).json())


def test_draft_query_user_id_cannot_switch_identity(session, client, owner_headers):
    seed_draft(session, OTHER_ID, "theirs")

    resp = client.get(f"/api/drafts/?user_id={OTHER_ID}", headers=owner_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_draft_body_user_id_cannot_switch_identity(session, client, owner_headers):
    resp = client.post(
        "/api/drafts/",
        json={"topic": "hijack", "user_id": str(OTHER_ID)},
        headers=owner_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_draft_body_user_id_matching_credential_is_accepted(session, client, owner_headers):
    resp = client.post(
        "/api/drafts/",
        json={"topic": "self addressed", "user_id": str(OWNER_ID)},
        headers=owner_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user_id"] == str(OWNER_ID)


def test_cross_user_draft_access_is_forbidden(session, client, other_headers):
    draft_id = seed_draft(session, OWNER_ID, "private")

    cases = [
        client.get(f"/api/drafts/{draft_id}", headers=other_headers),
        client.put(f"/api/drafts/{draft_id}", json={"topic": "hijack"}, headers=other_headers),
        client.patch(f"/api/drafts/{draft_id}", json={"topic": "hijack"}, headers=other_headers),
        client.delete(f"/api/drafts/{draft_id}", headers=other_headers),
        client.get(f"/api/drafts/{draft_id}/feedback", headers=other_headers),
        client.get(f"/api/drafts/{draft_id}/lineage", headers=other_headers),
        client.post(
            f"/api/drafts/{draft_id}/feedback",
            json={"comments_text": "hi"},
            headers=other_headers,
        ),
    ]
    for resp in cases:
        assert resp.status_code == 403, resp.text
        body = resp.json()
        assert body["error"]["code"] == "FORBIDDEN", body
        # The message must not confirm the resource exists for another user.
        assert body["error"]["message"] == "You do not have access to this resource."


def test_missing_draft_is_not_found(session, client, owner_headers):
    missing = str(uuid.uuid4())
    resp = client.get(f"/api/drafts/{missing}", headers=owner_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_cross_user_draft_save_is_forbidden(session, client, other_headers):
    """Overwriting another user's draft id must not be possible."""
    draft_id = seed_draft(session, OWNER_ID, "private")
    resp = client.post(
        "/api/drafts/",
        json={"id": draft_id, "topic": "hijack", "user_final_draft": "hijacked"},
        headers=other_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    # Untouched for the real owner.
    owner_view = client.get(f"/api/drafts/{draft_id}", headers={"Authorization": f"Bearer {OWNER_KEY}"})
    assert owner_view.status_code == 200
    assert owner_view.json()["user_final_draft"] == "user text"


def test_feedback_records_owner_identity_from_credential(session, client, owner_headers):
    draft_id = seed_draft(session, OWNER_ID, "feedback target")
    resp = client.post(
        f"/api/drafts/{draft_id}/feedback",
        json={"comments_text": "great post"},
        headers=owner_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user_id"] == str(OWNER_ID)


def test_feedback_body_user_id_mismatch_is_forbidden(session, client, owner_headers):
    draft_id = seed_draft(session, OWNER_ID, "feedback target")
    resp = client.post(
        f"/api/drafts/{draft_id}/feedback",
        json={"comments_text": "great post", "user_id": str(OTHER_ID)},
        headers=owner_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_blueprint_and_platform_routes_require_credentials(session, client):
    for resp in (
        client.get("/api/blueprints/"),
        client.get("/api/platforms/credentials"),
        client.get("/api/platforms/accounts"),
    ):
        assert resp.status_code == 401, resp.text
        assert resp.json()["error"]["code"] == "AUTH_REQUIRED"


def seed_profile_blueprint(session: Session, owner: uuid.UUID, bp_id: str, title: str) -> None:
    """Blueprints live inside ``User.profile_data``; there is no POST create route."""
    user = session.get(User, owner)
    assert user is not None
    data = dict(user.profile_data or {})
    bps = list(data.get("benchmark_blueprints") or [])
    bps.append({"id": bp_id, "title": title, "hook_style": "h", "structural_stages": []})
    data["benchmark_blueprints"] = bps
    user.profile_data = data
    session.add(user)
    session.commit()


def test_blueprint_routes_are_scoped_to_the_caller(session, client, owner_headers, other_headers):
    """The pre-existing ownership model answers 404 for another user's rows."""
    bp_id = "sec2-bp-1"
    seed_profile_blueprint(session, OWNER_ID, bp_id, "owner blueprint")
    assert client.get(f"/api/blueprints/{bp_id}", headers=owner_headers).status_code == 200

    for resp in (
        client.get(f"/api/blueprints/{bp_id}", headers=other_headers),
        client.put(f"/api/blueprints/{bp_id}", json={"title": "hijack"}, headers=other_headers),
        client.delete(f"/api/blueprints/{bp_id}", headers=other_headers),
    ):
        assert resp.status_code == 404, resp.text
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    assert client.get(f"/api/blueprints/{bp_id}", headers=owner_headers).status_code == 200


def test_platform_credentials_are_scoped_to_the_caller(session, client, owner_headers, other_headers):
    from app.models.credential import PlatformAccountCredential

    cred = PlatformAccountCredential(user_id=OWNER_ID, platform="zhihu", account_identifier="sec2-acct")
    session.add(cred)
    session.commit()
    session.refresh(cred)

    assert client.delete(f"/api/platforms/credentials/{cred.id}", headers=other_headers).status_code == 404
    assert client.get("/api/platforms/credentials", headers=other_headers).json() == []
    assert client.get("/api/platforms/credentials", headers=owner_headers).json()
    assert client.delete(f"/api/platforms/credentials/{cred.id}", headers=owner_headers).status_code == 200
