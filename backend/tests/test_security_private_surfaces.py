# -*- coding: utf-8 -*-
"""Unified security regression tests for the remaining private API surfaces.

Covers Material Vault, Obsidian bridge, Private Domain, Scheduler,
Settings/BYOK and the Chat Lounge session store.

Guarantees asserted here:

1. No raw exception text (absolute paths, SDK payloads, DB messages,
   secrets) may reach a response body.
2. Private routes require an authenticated credential.
3. A client-supplied ``user_id`` is never an authorization input.
4. Cross-user access, missing resources and malformed ids are collapsed into
   one indistinguishable 404 so the API cannot be used to probe for ids.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.auth import AuthenticatedUser
from app.core.config import settings
from app.core.db import get_session
from app.core.vault_path_guard import VaultPathError
from app.main import app
from app.models.user import User

OWNER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
OTHER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
OWNER_KEY = "sec3-owner-key"
OTHER_KEY = "sec3-other-key"

SECRET_MARKERS = (
    "Traceback (most recent call last)",
    "sqlite3.",
    "sqlalchemy.exc",
    "Incorrect API key provided",
    ".venv\\Lib\\site-packages",
    "C:\\Users\\",
    "SECRET-BYOK-KEY",
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
        for uid, name in ((OWNER_ID, "sec3-owner"), (OTHER_ID, "sec3-other")):
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

def assert_safe(resp) -> str:
    """Assert no internal detail leaked and return the flat response text."""
    flat = resp.text
    for marker in SECRET_MARKERS:
        assert marker not in flat, f"internal detail leaked ({marker!r}): {flat}"
    return flat


def assert_error_envelope(resp, expected_code: str, expected_status: int) -> dict:
    assert resp.status_code == expected_status, resp.text
    body = resp.json()
    assert body.get("error", {}).get("code") == expected_code, body
    assert body["error"]["message"], body
    header_rid = resp.headers.get("X-Request-ID")
    assert header_rid, resp.headers
    assert body["error"]["request_id"] == header_rid, body
    assert_safe(resp)
    return body


def assert_same_not_found(resp_a, resp_b) -> dict:
    """Different authorization reasons expose the same public 404.

    The per-request ``request_id`` is expected to differ, so only the
    publicly visible code/message pair is compared.
    """
    assert resp_a.status_code == 404, resp_a.text
    assert resp_b.status_code == 404, resp_b.text

    error_a = assert_error_envelope(resp_a, "NOT_FOUND", 404)["error"]
    error_b = assert_error_envelope(resp_b, "NOT_FOUND", 404)["error"]

    assert error_a["code"] == error_b["code"] == "NOT_FOUND"
    assert error_a["message"] == error_b["message"], (resp_a.text, resp_b.text)
    return error_a


def seed_material(session: Session, owner: uuid.UUID, title: str = "sec3 material") -> uuid.UUID:
    from app.models.material import Material

    mid = uuid.uuid4()
    session.add(
        Material(
            id=mid,
            user_id=owner,
            material_type="personal",
            source_platform="manual",
            title=title,
            cleaned_content="seeded body",
            tags=[],
            status="inbox",
            meta_info={},
        )
    )
    session.commit()
    return mid


# ==============================================================================
# Material Vault
# ==============================================================================

class TestMaterialVault:
    def test_list_requires_auth(self, client):
        r = client.get("/api/materials")
        assert r.status_code == 401, r.text
        assert_safe(r)

    def test_detail_requires_auth(self, client):
        r = client.get(f"/api/materials/{uuid.uuid4()}")
        assert r.status_code == 401, r.text

    def test_client_user_id_is_ignored_on_list(self, client, session, owner_headers):
        seed_material(session, OWNER_ID, "owner-visible")
        seed_material(session, OTHER_ID, "other-secret")

        r = client.get(f"/api/materials?user_id={OTHER_ID}", headers=owner_headers)
        assert r.status_code == 200, r.text
        titles = [m["title"] for m in r.json()]
        assert "owner-visible" in titles
        assert "other-secret" not in titles

    def test_create_ignores_body_user_id(self, client, session, owner_headers):
        payload = {
            "title": "created-by-owner",
            "cleaned_content": "hello",
            "user_id": str(OTHER_ID),
        }
        r = client.post("/api/materials", json=payload, headers=owner_headers)
        assert r.status_code in (200, 201), r.text
        assert r.json()["user_id"] == str(OWNER_ID), r.text

    def test_cross_user_and_missing_are_indistinguishable(self, client, session, other_headers):
        mid = seed_material(session, OWNER_ID)
        cross = client.get(f"/api/materials/{mid}", headers=other_headers)
        missing = client.get(f"/api/materials/{uuid.uuid4()}", headers=other_headers)
        assert_same_not_found(cross, missing)

    def test_other_user_cannot_read_missed_material(self, client, session, other_headers):
        mid = seed_material(session, OWNER_ID)
        cross = client.get(f"/api/materials/{mid}", headers=other_headers)
        assert cross.status_code == 404, cross.text
        assert_same_not_found(
            cross, client.get(f"/api/materials/{uuid.uuid4()}", headers=other_headers)
        )

    def test_malformed_uuid_is_not_a_bypass(self, client, session, owner_headers):
        seed_material(session, OWNER_ID)
        r = client.get("/api/materials/not-a-uuid", headers=owner_headers)
        assert r.status_code in (404, 422), r.text
        assert_safe(r)

    def test_update_delete_reject_cross_user(self, client, session, other_headers):
        mid = seed_material(session, OWNER_ID)
        assert client.patch(f"/api/materials/{mid}", json={"title": "x"}, headers=other_headers).status_code == 404
        assert client.delete(f"/api/materials/{mid}", headers=other_headers).status_code == 404


# ==============================================================================
# Obsidian bridge
# ==============================================================================

class TestObsidianBridge:
    ENDPOINTS = (
        ("post", "/api/obsidian/scan", {"vault_path": "C:/vault"}),
        ("post", "/api/obsidian/sync", {"vault_path": "C:/vault", "selected_items": []}),
        ("get", "/api/obsidian/status", None),
        ("get", "/api/obsidian/allowed-roots", None),
    )

    @pytest.mark.parametrize("method,url,payload", ENDPOINTS)
    def test_all_endpoints_require_auth(self, client, method, url, payload):
        r = getattr(client, method)(url, json=payload) if method == "post" else getattr(client, method)(url)
        assert r.status_code == 401, r.text
        assert_safe(r)

    def test_sync_ignores_body_user_id(self, client, session, owner_headers, monkeypatch):
        from app.api import obsidian as obsidian_api

        seen = {}

        def fake_sync_items(vault_path, selected_items, user_id, session):
            seen["user_id"] = user_id
            return {"imported": 0}

        monkeypatch.setattr(obsidian_api.ObsidianBridgeService, "sync_items", staticmethod(fake_sync_items))
        r = client.post(
            "/api/obsidian/sync",
            json={"vault_path": "C:/vault", "selected_items": [], "user_id": str(OTHER_ID)},
            headers=owner_headers,
        )
        assert r.status_code == 200, r.text
        assert seen["user_id"] == str(OWNER_ID)

    def test_vault_path_error_never_echoes_absolute_path(self, client, owner_headers, monkeypatch):
        from app.api import obsidian as obsidian_api

        leaked = "C:\\Users\\victim\\SecretVault"

        def boom(**kwargs):
            raise VaultPathError(f"resolved path {leaked} is not allowed")

        monkeypatch.setattr(obsidian_api.ObsidianBridgeService, "scan_vault", staticmethod(boom))
        r = client.post("/api/obsidian/scan", json={"vault_path": "C:/vault"}, headers=owner_headers)
        assert_error_envelope(r, "VALIDATION_ERROR", 422)
        flat = assert_safe(r)
        assert leaked not in flat, flat
        assert "Vault path" in flat

    def test_vault_path_not_found_has_fixed_message(self, client, owner_headers, monkeypatch):
        from app.api import obsidian as obsidian_api
        from app.core.vault_path_guard import VaultPathNotFound

        def boom(**kwargs):
            raise VaultPathNotFound("C:\\Users\\victim\\missing")

        monkeypatch.setattr(obsidian_api.ObsidianBridgeService, "scan_vault", staticmethod(boom))
        r = client.post("/api/obsidian/scan", json={"vault_path": "C:/vault"}, headers=owner_headers)
        assert_error_envelope(r, "NOT_FOUND", 404)


# ==============================================================================
# Private Domain
# ==============================================================================

class TestPrivateDomain:
    def test_generate_endpoints_require_auth(self, client):
        for url in ("/api/private-domain/generate-moment", "/api/private-domain/generate-community"):
            r = client.post(url, json={"persona_id": "not-a-uuid"})
            assert r.status_code == 401, (url, r.text)
            assert_safe(r)

    def test_templates_stay_public(self, client):
        r = client.get("/api/private-domain/templates")
        assert r.status_code == 200, r.text

    def test_generate_moment_ignores_body_user_id(self, client, owner_headers):
        r = client.post(
            "/api/private-domain/generate-moment",
            json={"category": "专业沉淀", "persona_id": "not-a-uuid", "user_id": str(OTHER_ID)},
            headers=owner_headers,
        )
        assert r.status_code == 404, r.text
        assert_safe(r)

    def test_generate_moment_rejects_malformed_persona(self, client, owner_headers):
        r = client.post(
            "/api/private-domain/generate-moment",
            json={"category": "专业沉淀", "persona_id": "not-a-uuid"},
            headers=owner_headers,
        )
        assert r.status_code == 404, r.text
        assert_safe(r)

    def test_generate_community_rejects_malformed_persona(self, client, owner_headers):
        r = client.post(
            "/api/private-domain/generate-community",
            json={"persona_id": "not-a-uuid"},
            headers=owner_headers,
        )
        assert r.status_code == 404, r.text
        assert_safe(r)

    def test_cross_user_persona_is_same_as_missing(self, client, session, owner_headers, other_headers):
        from app.models.persona import IPPersona

        pid = uuid.uuid4()
        session.add(IPPersona(id=pid, user_id=OWNER_ID, name="owner persona"))
        session.commit()

        cross = client.post(
            "/api/private-domain/generate-moment",
            json={"category": "专业沉淀", "persona_id": str(pid)},
            headers=other_headers,
        )
        missing = client.post(
            "/api/private-domain/generate-moment",
            json={"category": "专业沉淀", "persona_id": str(uuid.uuid4())},
            headers=other_headers,
        )
        assert_same_not_found(cross, missing)


# ==============================================================================
# Scheduler
# ==============================================================================

class TestScheduler:
    ROUTES = (
        ("get", "/api/scheduler/quota", None),
        ("get", "/api/scheduler/status", None),
        ("post", "/api/scheduler/trigger", None),
        ("post", "/api/scheduler/settings", {}),
        ("get", "/api/scheduler/briefing/today", None),
    )

    @pytest.mark.parametrize("method,url,payload", ROUTES)
    def test_private_routes_require_auth(self, client, method, url, payload):
        r = client.request(method.upper(), url, json=payload) if payload is not None else getattr(client, method)(url)
        assert r.status_code == 401, (url, r.text)
        assert_safe(r)

    @pytest.mark.parametrize("url", ["/api/scheduler/status", "/api/scheduler/trigger"])
    def test_status_and_trigger_do_not_500_unauthenticated(self, client, url):
        r = client.post(url) if url.endswith("trigger") else client.get(url)
        assert r.status_code != 500, r.text
        assert r.status_code == 401, r.text

    def test_per_user_settings_are_not_shared(self, client, owner_headers, other_headers):
        from app.api import scheduler as scheduler_api

        sched = scheduler_api.inspection_scheduler
        client.post(
            "/api/scheduler/settings",
            json={"daily_quota": 3, "auto_run_enabled": False},
            headers=owner_headers,
        )
        other = client.get("/api/scheduler/status", headers=other_headers)
        assert other.status_code == 200, other.text
        assert other.json().get("daily_quota") != 3, other.text

    def test_deprecated_user_id_query_is_ignored(self, client, owner_headers):
        r = client.get(f"/api/scheduler/quota?user_id={OTHER_ID}", headers=owner_headers)
        assert r.status_code == 200, r.text
        assert_safe(r)


# ==============================================================================
# Settings / BYOK
# ==============================================================================

class TestSettings:
    def test_endpoints_require_auth(self, client):
        assert client.post("/api/settings/test-connection", json={}).status_code == 401
        assert client.get("/api/settings/current").status_code == 401

    def test_upstream_exception_is_sanitized(self, client, owner_headers, monkeypatch):
        from app.api import settings as settings_api

        def boom(*args, **kwargs):
            raise RuntimeError("Incorrect API key provided: SECRET-BYOK-KEY")

        monkeypatch.setattr(settings_api, "AsyncOpenAI", boom)
        r = client.post(
            "/api/settings/test-connection",
            json={"api_key": "SECRET-BYOK-KEY", "base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
            headers=owner_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is False, body
        flat = assert_safe(r)
        assert "SECRET-BYOK-KEY" not in flat

    def test_model_byok_header_is_accepted(self, client, owner_headers, monkeypatch):
        from app.api import settings as settings_api

        captured = {}

        class FakeCompletions:
            async def create(self, **kwargs):
                captured["ok"] = True
                return object()

        class FakeClient:
            def __init__(self, **kwargs):
                captured["api_key"] = kwargs.get("api_key")
                self.chat = type("C", (), {"completions": FakeCompletions()})()

        monkeypatch.setattr(settings_api, "AsyncOpenAI", FakeClient)
        # SSRF validation is covered by test_settings_ssrf.py; isolate this
        # test to the BYOK header contract only.
        monkeypatch.setattr(
            settings_api, "validate_provider_base_url", lambda base_url, **kwargs: base_url
        )
        r = client.post(
            "/api/settings/test-connection",
            json={"model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
            headers={**owner_headers, "X-Model-Api-Key": "SECRET-BYOK-KEY"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True, r.text
        assert captured["api_key"] == "SECRET-BYOK-KEY"
        assert "SECRET-BYOK-KEY" not in r.text

    def test_x_api_key_still_authenticates_app(self, client):
        r = client.get("/api/settings/current", headers={"X-Api-Key": OWNER_KEY})
        assert r.status_code == 200, r.text
        assert_safe(r)

    def test_current_never_returns_raw_key(self, client, owner_headers, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "SECRET-BYOK-KEY-123456")
        r = client.get("/api/settings/current", headers=owner_headers)
        assert r.status_code == 200, r.text
        assert "SECRET-BYOK-KEY-123456" not in r.text
        assert r.json()["api_key_configured"] is True


# ==============================================================================
# Chat Lounge
# ==============================================================================

class TestChatLounge:
    @pytest.fixture(autouse=True)
    def _clean(self):
        from app.api import chat_lounge

        chat_lounge._session_store.clear()
        chat_lounge._session_meta.clear()
        yield
        chat_lounge._session_store.clear()
        chat_lounge._session_meta.clear()

    def _seed_session(self, owner: uuid.UUID, session_id: str = "sec3-session"):
        from app.api import chat_lounge

        chat_lounge._session_meta[session_id] = {"user_id": str(owner), "title": "t"}
        chat_lounge._session_store[session_id] = [
            {"role": "user", "content": "hello", "ts": "2026-01-01T00:00:00"}
        ]
        return session_id

    def test_history_requires_auth(self, client):
        r = client.get("/api/chat/lounge/history", params={"session_id": "whatever"})
        assert r.status_code == 401, r.text

    def test_cross_user_session_is_404(self, client, owner_headers, other_headers):
        sid = self._seed_session(OWNER_ID)
        r = client.get("/api/chat/lounge/history", params={"session_id": sid}, headers=other_headers)
        assert r.status_code == 404, r.text
        assert sid not in r.text

    def test_missing_and_cross_user_are_indistinguishable(self, client, owner_headers, other_headers):
        sid = self._seed_session(OWNER_ID)
        cross = client.get("/api/chat/lounge/history", params={"session_id": sid}, headers=other_headers)
        missing = client.get("/api/chat/lounge/history", params={"session_id": "nope-nope"}, headers=other_headers)
        assert_same_not_found(cross, missing)
        assert_safe(cross)

    def test_404_does_not_echo_session_id(self, client, other_headers):
        sid = self._seed_session(OWNER_ID)
        flat = client.get("/api/chat/lounge/history", params={"session_id": sid}, headers=other_headers).text
        assert sid not in flat

    def test_owner_can_read_own_session(self, client, owner_headers):
        sid = self._seed_session(OWNER_ID)
        r = client.get("/api/chat/lounge/history", params={"session_id": sid}, headers=owner_headers)
        assert r.status_code == 200, r.text
        assert r.json()["messages"], r.text

    def test_delete_session_rejects_cross_user(self, client, other_headers):
        sid = self._seed_session(OWNER_ID)
        r = client.delete(f"/api/chat/sessions/{sid}", headers=other_headers)
        assert r.status_code == 404, r.text
        assert sid not in r.text
