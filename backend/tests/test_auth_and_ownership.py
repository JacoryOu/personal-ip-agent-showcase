# -*- coding: utf-8 -*-
"""P0 security regression tests: authentication + object ownership (IDOR).

These tests assert two things:

1. Identity is derived *only* from the presented credential. A ``user_id``
   in the query string or body must never select another user's data.
2. Every write/read path that addresses an existing object verifies ownership
   first and answers 404 (never 403) so existence is not leaked.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.chat_lounge import _session_meta, _session_store
from app.core.auth import AuthenticatedUser, resolve_user_from_key
from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.models.benchmark_account import BenchmarkAccount
from app.models.credential import PlatformAccountCredential
from app.models.user import User

OWNER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
OTHER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
OWNER_KEY = "owner-secret-key"
OTHER_KEY = "other-secret-key"


@pytest.fixture
def auth_settings():
    """Configure explicit multi-user API-key auth (no local-dev fallback)."""
    old_keys = settings.API_KEYS
    old_local = settings.AUTH_LOCAL_DEV_MODE
    old_required = settings.AUTH_REQUIRED
    settings.API_KEYS = f"{OWNER_ID}={OWNER_KEY},{OTHER_ID}={OTHER_KEY}"
    settings.AUTH_LOCAL_DEV_MODE = False
    settings.AUTH_REQUIRED = True
    try:
        yield
    finally:
        settings.API_KEYS = old_keys
        settings.AUTH_LOCAL_DEV_MODE = old_local
        settings.AUTH_REQUIRED = old_required


@pytest.fixture
def owner_headers():
    return {"Authorization": f"Bearer {OWNER_KEY}"}


@pytest.fixture
def other_headers():
    return {"Authorization": f"Bearer {OTHER_KEY}"}


@pytest.fixture(name="test_engine")
def _engine_fixture():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture(name="session")
def _session_fixture(test_engine):
    with Session(test_engine) as sess:
        yield sess


@pytest.fixture
def client(session: Session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def users(session: Session):
    for uid, username in ((OWNER_ID, "sec-owner"), (OTHER_ID, "sec-other")):
        if not session.get(User, uid):
            session.add(User(id=uid, username=username))
    session.commit()
    return session


# ==============================================================================
# Authentication behaviour
# ==============================================================================

def test_missing_credentials_are_rejected(auth_settings):
    with TestClient(app) as client:
        resp = client.get("/api/blueprints/")
    assert resp.status_code == 401


def test_invalid_key_is_rejected_even_with_local_dev_mode():
    settings.API_KEYS = f"{OWNER_ID}={OWNER_KEY}"
    settings.AUTH_LOCAL_DEV_MODE = True
    settings.AUTH_REQUIRED = False
    try:
        with TestClient(app) as client:
            resp = client.get("/api/blueprints/", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401
    finally:
        settings.API_KEYS = ""
        settings.AUTH_LOCAL_DEV_MODE = False


def test_bearer_and_api_key_map_to_configured_users(auth_settings):
    assert resolve_user_from_key(OWNER_KEY).id == OWNER_ID
    assert resolve_user_from_key(OTHER_KEY).id == OTHER_ID

    with TestClient(app) as client:
        bearer = client.get("/api/blueprints/", headers={"Authorization": f"Bearer {OWNER_KEY}"})
        api_key = client.get("/api/blueprints/", headers={"X-API-Key": OWNER_KEY})
    assert bearer.status_code == 200
    assert api_key.status_code == 200


def test_local_dev_fallback_requires_explicit_opt_in():
    settings.API_KEYS = ""
    settings.AUTH_REQUIRED = False
    settings.AUTH_LOCAL_DEV_MODE = False
    try:
        with TestClient(app) as client:
            assert client.get("/api/blueprints/").status_code == 401
            settings.AUTH_LOCAL_DEV_MODE = True
            assert client.get("/api/blueprints/").status_code == 200
    finally:
        settings.AUTH_LOCAL_DEV_MODE = False


# ==============================================================================
# IDOR: benchmark blueprints (profile-scoped objects)
# ==============================================================================

def _seed_blueprint(session: Session, user_id: uuid.UUID, bp_id: str, title: str):
    user = session.get(User, user_id)
    assert user is not None
    data = dict(user.profile_data or {})
    bps = list(data.get("benchmark_blueprints") or [])
    bps.append({"id": bp_id, "title": title, "hook_style": "h", "structural_stages": []})
    data["benchmark_blueprints"] = bps
    user.profile_data = data
    session.add(user)
    session.commit()


def _read_blueprint_title(session: Session, user_id: uuid.UUID, bp_id: str):
    user = session.get(User, user_id)
    for bp in (user.profile_data or {}).get("benchmark_blueprints") or []:
        if bp.get("id") == bp_id:
            return bp.get("title")
    return None


def test_blueprint_cross_user_read_update_delete_is_404(auth_settings, users, client, owner_headers):
    bp_id = "sec-bp-1"
    _seed_blueprint(users, OWNER_ID, bp_id, "owner title")
    if True:
        assert client.get(f"/api/blueprints/{bp_id}", headers=owner_headers).status_code == 200

        assert client.get(f"/api/blueprints/{bp_id}", headers={"Authorization": f"Bearer {OTHER_KEY}"}).status_code == 404

        upd = client.put(f"/api/blueprints/{bp_id}", json={"title": "hijacked"}, headers={"Authorization": f"Bearer {OTHER_KEY}"})
        assert upd.status_code == 404

        patch = client.patch(f"/api/blueprints/{bp_id}", json={"title": "hijacked"}, headers={"Authorization": f"Bearer {OTHER_KEY}"})
        assert patch.status_code == 404

        dele = client.delete(f"/api/blueprints/{bp_id}", headers={"Authorization": f"Bearer {OTHER_KEY}"})
        assert dele.status_code == 404

    assert _read_blueprint_title(users, OWNER_ID, bp_id) == "owner title"


def test_blueprint_body_user_id_cannot_switch_identity(auth_settings, users, client, owner_headers):
    bp_id = "sec-bp-2"
    _seed_blueprint(users, OTHER_ID, bp_id, "other title")
    if True:
        # Caller authenticates as OWNER but claims OTHER_ID in the body.
        resp = client.get(f"/api/blueprints/{bp_id}?user_id={OTHER_ID}", headers=owner_headers)
    assert resp.status_code == 404


# ==============================================================================
# IDOR: platform accounts / credentials
# ==============================================================================

def _seed_account(session: Session, user_id: uuid.UUID, account_id: str):
    acct = BenchmarkAccount(
        user_id=user_id,
        platform="wechat",
        account_name=account_id,
        account_id=account_id,
    )
    session.add(acct)
    session.commit()
    session.refresh(acct)
    return acct


def test_account_cross_user_delete_and_sync_is_404(auth_settings, users, client, owner_headers):
    acct = _seed_account(users, OWNER_ID, "sec-acct-1")
    other = {"Authorization": f"Bearer {OTHER_KEY}"}
    if True:
        assert client.delete(f"/api/platforms/accounts/{acct.id}", headers=other).status_code == 404
        assert client.post(f"/api/platforms/accounts/{acct.id}/sync", headers=other).status_code == 404
        assert client.get(f"/api/platforms/accounts/{acct.id}/feed", headers=other).status_code == 404
    # Owner can still delete it -> proves the row survived the hostile attempts.
    assert client.delete(f"/api/platforms/accounts/{acct.id}", headers=owner_headers).status_code == 200


def test_credential_cross_user_delete_is_404(auth_settings, users, client, owner_headers):
    cred = PlatformAccountCredential(user_id=OWNER_ID, platform="zhihu", account_identifier="sec-cred")
    users.add(cred)
    users.commit()
    users.refresh(cred)
    other = {"Authorization": f"Bearer {OTHER_KEY}"}
    assert client.delete(f"/api/platforms/credentials/{cred.id}", headers=other).status_code == 404
    assert client.get("/api/platforms/credentials", headers=other).json() == []
    assert client.delete(f"/api/platforms/credentials/{cred.id}", headers=owner_headers).status_code == 200


# ==============================================================================
# IDOR: chat lounge sessions
# ==============================================================================

def _seed_chat_session(session_id: str, owner: str):
    _session_store[session_id] = [{"role": "user", "content": "hi", "ts": "2026-01-01T00:00:00Z"}]
    _session_meta[session_id] = {"user_id": owner, "mode": "interview", "title": "t"}


def test_chat_session_cross_user_access_is_404(auth_settings, owner_headers):
    sid = "sec-chat-1"
    _seed_chat_session(sid, str(OWNER_ID))
    other = {"Authorization": f"Bearer {OTHER_KEY}"}
    try:
        with TestClient(app) as client:
            assert client.get(f"/api/chat/lounge/history?session_id={sid}", headers=other).status_code == 404
            assert client.post(f"/api/chat/lounge/sessions/{sid}/title", json={"title": "x"}, headers=other).status_code == 404
            assert client.delete(f"/api/chat/lounge/sessions/{sid}", headers=other).status_code == 404
            assert client.post(f"/api/chat/lounge/sessions/{sid}/crystallize-persona", headers=other).status_code == 404
        # Untouched for the real owner.
        assert sid in _session_store
        assert _session_meta[sid].get("title") == "t"
        with TestClient(app) as client:
            assert client.get(f"/api/chat/lounge/history?session_id={sid}", headers=owner_headers).status_code == 200
    finally:
        _session_store.pop(sid, None)
        _session_meta.pop(sid, None)


def test_chat_sessions_list_only_returns_caller_sessions(auth_settings, owner_headers):
    _seed_chat_session("sec-chat-owner", str(OWNER_ID))
    _seed_chat_session("sec-chat-other", str(OTHER_ID))
    try:
        with TestClient(app) as client:
            ids = {s["session_id"] for s in client.get("/api/chat/lounge/sessions?user_id=" + str(OTHER_ID), headers=owner_headers).json()}
        assert "sec-chat-owner" in ids
        assert "sec-chat-other" not in ids
    finally:
        _session_store.pop("sec-chat-owner", None)
        _session_meta.pop("sec-chat-owner", None)
        _session_store.pop("sec-chat-other", None)
        _session_meta.pop("sec-chat-other", None)
