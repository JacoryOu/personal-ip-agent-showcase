# -*- coding: utf-8 -*-
"""Tests for security line C: vault path allow-list + inspection quota.

Covers:
- Obsidian vault path validation (allow-list, traversal, symlink escape, 4xx).
- Inspection external-call pre-authorization, per-run/daily quota, enable switch.
- Observability of denied runs and skill failures.
- Scheduler API no longer trusts a caller-supplied user_id.
"""
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.skill_engine.policy import ExecutionContext
from app.core.vault_path_guard import (
    VaultPathError,
    VaultPathNotFound,
    get_allowed_roots,
    validate_vault_path,
)
from app.main import app
from app.core.db import get_session
from app.models.inspection_quota import InspectionQuota
from app.models.material import Material
from app.models.user import User
from app.services.inspection_quota_service import (
    check_and_consume,
    get_status,
    reset_run,
    set_grant,
)
from app.services.inspection_scheduler_service import inspection_scheduler


class _FakeResult:
    def __init__(self, success=True, output=None, error=None):
        self.success = success
        self.output = output
        self.error = error


class _FakeSkillManager:
    """Minimal stand-in for SkillManager that records execute_skill_sync calls."""

    def __init__(self, calls):
        self._calls = calls

    def execute_skill_sync(self, name, payload, execution_context=None):
        self._calls["n"] += 1
        self._calls["skills"] = self._calls.get("skills", []) + [name]
        # Recorded so the test can assert the scheduler explicitly marks the
        # run as unattended instead of relying on a process-wide env var.
        self._calls["execution_context"] = execution_context
        return _FakeResult(success=True, output=[])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(id=uuid.uuid4(), username="sec_path_user", profile_data={})
        session.add(user)
        session.commit()
        session.refresh(user)
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unattended_pre_authorization(monkeypatch):
    """Grant the two independent unattended layers for one test.

    Scheduler runs are deny-by-default at both the workflow permission layer
    (``COG_WORKFLOW_PRE_AUTHORIZED``) and the skill permission policy
    (``COG_SKILL_*``). A test that wants the cycle to actually run must grant
    both explicitly; a test that expects a denial simply does not use this
    fixture, which is what proves the fail-closed default.
    """
    from app.core.workflow_permissions import (
        ENV_PRE_AUTHORIZED,
        PERM_NETWORK_EGRESS,
        PERM_SKILL_EXEC,
        SKILL_CAP_FS_ISOLATED,
        SKILL_CAP_NETWORK_READ,
    )

    monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_HOSTS", "example.test")
    monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_UNATTENDED", "1")
    monkeypatch.setenv(
        "COG_SKILL_UNATTENDED_ALLOW_PERMISSIONS",
        f"{SKILL_CAP_NETWORK_READ},{SKILL_CAP_FS_ISOLATED}",
    )
    monkeypatch.setenv(
        ENV_PRE_AUTHORIZED,
        ",".join(
            [
                PERM_NETWORK_EGRESS,
                PERM_SKILL_EXEC,
                SKILL_CAP_NETWORK_READ,
                SKILL_CAP_FS_ISOLATED,
            ]
        ),
    )


@pytest.fixture
def allowed_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "vaults"
    root.mkdir()
    monkeypatch.setenv("OBSIDIAN_ALLOWED_ROOTS", str(root))
    return root


# ---------------------------------------------------------------------------
# Vault path guard
# ---------------------------------------------------------------------------

class TestVaultPathGuard:
    def test_path_inside_allowed_root_is_accepted(self, allowed_root: Path):
        vault = allowed_root / "my-vault"
        vault.mkdir()
        resolved, matched = validate_vault_path(str(vault))
        assert resolved == vault.resolve()
        assert matched == allowed_root.resolve()

    def test_relative_traversal_is_rejected(self, allowed_root: Path):
        vault = allowed_root / "v"
        vault.mkdir()
        escape = allowed_root / "v" / ".." / ".." / "outside"
        with pytest.raises(VaultPathError):
            validate_vault_path(str(escape))

    def test_absolute_outside_path_is_rejected(self, tmp_path: Path, monkeypatch):
        root = tmp_path / "vaults"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.setenv("OBSIDIAN_ALLOWED_ROOTS", str(root))
        with pytest.raises(VaultPathError):
            validate_vault_path(str(outside))

    def test_empty_path_is_rejected(self):
        with pytest.raises(VaultPathError):
            validate_vault_path("")

    def test_missing_allowed_path_is_404(self, allowed_root: Path):
        with pytest.raises(VaultPathNotFound) as exc_info:
            validate_vault_path(str(allowed_root / "nope"))
        assert exc_info.value.http_status == 404

    def test_symlink_escape_is_rejected(self, allowed_root: Path, tmp_path: Path):
        secret = tmp_path / "secret"
        secret.mkdir()
        (secret / "leak.md").write_text("top secret", encoding="utf-8")
        link = allowed_root / "escape"
        try:
            link.symlink_to(secret, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation not permitted on this platform")
        # The symlink target is outside the allow-list, so it must be rejected
        # even though the link itself lives inside the allowed root.
        with pytest.raises(VaultPathError):
            validate_vault_path(str(link))

    def test_default_roots_are_project_local(self, monkeypatch):
        monkeypatch.delenv("OBSIDIAN_ALLOWED_ROOTS", raising=False)
        roots = get_allowed_roots()
        assert roots
        for r in roots:
            assert "obsidian_vaults" in r.name


# ---------------------------------------------------------------------------
# Inspection quota
# ---------------------------------------------------------------------------

class TestInspectionQuota:
    def test_default_is_fail_closed(self, session: Session):
        user = session.exec(select(User)).first()
        status = get_status(session, user.id)
        assert status["authorized"] is False
        decision = check_and_consume(session, user.id, runs=1)
        assert decision["allowed"] is False
        assert decision["reason"] == "not_pre_authorized"

    def test_grant_allows_within_limits(self, session: Session):
        user = session.exec(select(User)).first()
        set_grant(session, user.id, authorized=True, daily_limit=2, per_run_limit=2)
        decision = check_and_consume(session, user.id, runs=1)
        assert decision["allowed"] is True
        status = get_status(session, user.id)
        assert status["used_today"] == 1
        assert status["remaining_today"] == 1

    def test_disabled_switch_denies(self, session: Session):
        user = session.exec(select(User)).first()
        set_grant(session, user.id, authorized=True, enabled=False)
        decision = check_and_consume(session, user.id, runs=1)
        assert decision["allowed"] is False
        assert decision["reason"] == "scheduler_disabled"

    def test_per_run_limit_denies(self, session: Session):
        user = session.exec(select(User)).first()
        set_grant(session, user.id, authorized=True, daily_limit=10, per_run_limit=0)
        decision = check_and_consume(session, user.id, runs=1)
        assert decision["allowed"] is False
        assert decision["reason"] == "per_run_limit_exceeded"

    def test_daily_limit_denies_and_records(self, session: Session):
        user = session.exec(select(User)).first()
        set_grant(session, user.id, authorized=True, daily_limit=1, per_run_limit=5)
        assert check_and_consume(session, user.id, runs=1)["allowed"] is True
        q = session.exec(select(InspectionQuota)).first()
        reset_run(q)
        session.commit()
        decision = check_and_consume(session, user.id, runs=1)
        assert decision["allowed"] is False
        assert decision["reason"] == "daily_limit_exceeded"
        status = get_status(session, user.id)
        assert status["total_denied"] >= 1
        assert status["last_denial_reason"] == "daily_limit_exceeded"

    def test_quota_is_per_user(self, session: Session):
        user_a = session.exec(select(User)).first()
        user_b = User(id=uuid.uuid4(), username="other_user", profile_data={})
        session.add(user_b)
        session.commit()

        set_grant(session, user_a.id, authorized=True, daily_limit=1, per_run_limit=1)
        assert check_and_consume(session, user_a.id, runs=1)["allowed"] is True
        # User B is untouched and fails closed.
        decision_b = check_and_consume(session, user_b.id, runs=1)
        assert decision_b["allowed"] is False
        assert decision_b["reason"] == "not_pre_authorized"


# ---------------------------------------------------------------------------
# Scheduler behaviour under quota
# ---------------------------------------------------------------------------

class TestSchedulerQuotaIntegration:
    def test_cycle_denied_without_pre_authorization(self, session: Session, monkeypatch):
        user = session.exec(select(User)).first()

        calls = {"n": 0}

        def fake_skill(*args, **kwargs):
            calls["n"] += 1
            return []

        monkeypatch.setattr(
            "app.services.inspection_scheduler_service.get_skill_manager",
            lambda: _FakeSkillManager(calls),
        )

        result = inspection_scheduler.run_inspection_cycle(session=session, user_id=user.id)
        assert result["success"] is False
        assert calls["n"] == 0  # no external call attempted

    def test_cycle_runs_when_authorized(
        self,
        session: Session,
        monkeypatch,
        unattended_pre_authorization,
    ):
        user = session.exec(select(User)).first()
        set_grant(session, user.id, authorized=True, daily_limit=5, per_run_limit=5)

        calls = {"n": 0}

        def fake_skill(*args, **kwargs):
            calls["n"] += 1
            return []

        monkeypatch.setattr(
            "app.services.inspection_scheduler_service.get_skill_manager",
            lambda: _FakeSkillManager(calls),
        )
        result = inspection_scheduler.run_inspection_cycle(session=session, user_id=user.id)
        # Wheel1 consumed quota; even if the fake skill returned nothing the
        # cycle should not be denied for authorization reasons.
        assert calls["n"] >= 1
        # The scheduler must mark the run itself as unattended rather than
        # depending on COG_SKILL_EXECUTION_CONTEXT being set process-wide.
        assert calls["execution_context"] is ExecutionContext.UNATTENDED

    def test_cycle_denied_when_workflow_scope_missing(
        self,
        session: Session,
        monkeypatch,
    ):
        """Skill policy alone must not unlock the workflow layer."""
        user = session.exec(select(User)).first()
        set_grant(session, user.id, authorized=True, daily_limit=5, per_run_limit=5)

        calls = {"n": 0}

        def fake_skill(*args, **kwargs):
            calls["n"] += 1
            return []

        monkeypatch.setattr(
            "app.services.inspection_scheduler_service.get_skill_manager",
            lambda: _FakeSkillManager(calls),
        )
        # Only the skill capability layer is granted; the workflow
        # pre-authorization list stays empty.
        monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_HOSTS", "example.test")
        monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_UNATTENDED", "1")
        monkeypatch.setenv(
            "COG_SKILL_UNATTENDED_ALLOW_PERMISSIONS",
            "network:read,filesystem:isolated",
        )
        monkeypatch.setenv("COG_WORKFLOW_PRE_AUTHORIZED", "")

        inspection_scheduler.run_inspection_cycle(session=session, user_id=user.id)
        assert calls["n"] == 0


# ---------------------------------------------------------------------------
# Scheduler API: no caller-supplied user_id trust
# ---------------------------------------------------------------------------

class TestSchedulerApiTrust:
    def test_trigger_ignores_foreign_user_id(self, client: TestClient, session: Session):
        me = session.exec(select(User)).first()
        other = User(id=uuid.uuid4(), username="victim", profile_data={})
        session.add(other)
        session.commit()

        # Grant only the caller (default/first) user.
        set_grant(session, me.id, authorized=True, daily_limit=5, per_run_limit=5)

        resp = client.post(f"/api/scheduler/trigger?user_id={other.id}")
        assert resp.status_code == 200

        # The foreign user must not have been granted or consumed anything.
        other_status = get_status(session, other.id)
        assert other_status["authorized"] is False
        assert other_status["used_today"] == 0

    def test_quota_endpoints_roundtrip(self, client: TestClient, session: Session):
        me = session.exec(select(User)).first()

        resp = client.get("/api/scheduler/quota")
        assert resp.status_code == 200
        assert resp.json()["authorized"] is False

        resp = client.put(
            "/api/scheduler/quota",
            json={"authorized": True, "daily_limit": 3, "per_run_limit": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorized"] is True
        assert data["daily_limit"] == 3
        assert data["per_run_limit"] == 2

        resp = client.get("/api/scheduler/quota")
        assert resp.json()["authorized"] is True

    def test_status_includes_quota(self, client: TestClient):
        resp = client.get("/api/scheduler/status")
        assert resp.status_code == 200
        assert "inspection_quota" in resp.json()


# ---------------------------------------------------------------------------
# Obsidian API returns 4xx for disallowed vault
# ---------------------------------------------------------------------------

class TestObsidianApiPathGuard:
    def test_allowed_roots_endpoint(self, client: TestClient, allowed_root: Path):
        resp = client.get("/api/obsidian/allowed-roots")
        assert resp.status_code == 200
        assert str(allowed_root.resolve()) in resp.json()["allowed_roots"]

    def test_scan_outside_root_returns_4xx(self, client: TestClient, tmp_path: Path, monkeypatch):
        root = tmp_path / "vaults"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.setenv("OBSIDIAN_ALLOWED_ROOTS", str(root))
        resp = client.post("/api/obsidian/scan", json={"vault_path": str(outside)})
        assert 400 <= resp.status_code < 500

    def test_sync_outside_root_returns_4xx(self, client: TestClient, tmp_path: Path, monkeypatch):
        root = tmp_path / "vaults"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.setenv("OBSIDIAN_ALLOWED_ROOTS", str(root))
        resp = client.post("/api/obsidian/sync", json={"vault_path": str(outside)})
        assert 400 <= resp.status_code < 500
