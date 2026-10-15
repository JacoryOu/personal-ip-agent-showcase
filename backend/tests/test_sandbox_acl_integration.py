# -*- coding: utf-8 -*-
"""Integration tests for the scoped NTFS ACL layer inside the skill runner.

These tests pin the *wiring* between ``acl_guard`` and
``windows_sandbox.WindowsSandboxRunner``:

* ``acl_mode="enforce"`` is reachable (the profile must NOT fail closed on it).
* ``acl_mode="dry_run"`` never writes a DACL.
* The ACL is rolled back when the run ends -- including when the child fails.
* An ACL apply/verify failure fails closed and does NOT start a child.
* A rollback failure is surfaced on stderr, never silently swallowed.

What this still does NOT prove: AppContainer, an OS network boundary, or
recovery of an ACL left behind by a hard runner kill.
"""
from pathlib import Path
import sys

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest

from app.core.skill_engine import windows_sandbox as ws
from app.core.skill_engine.discovery import SkillDefinition
from app.core.skill_engine.windows_sandbox import (
    MODE_RESTRICTED_TOKEN,
    WindowsSandboxRunner,
)


ECHO_SKILL = """
import argparse, json

parser = argparse.ArgumentParser()
parser.add_argument("--file")
parser.add_argument("--json")
args, _ = parser.parse_known_args()

with open(args.file, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

print(json.dumps({"success": True, "echo": payload}))
"""

BOOM_SKILL = """
import sys
sys.stderr.write("boom")
sys.exit(3)
"""


@pytest.fixture
def echo_skill(tmp_path) -> SkillDefinition:
    skill_dir = tmp_path / "echo_skill"
    skill_dir.mkdir()
    (skill_dir / "main.py").write_text(ECHO_SKILL, encoding="utf-8")
    return SkillDefinition(
        name="echo_skill",
        description="Echoes back its input payload.",
        entrypoint="main.py",
        runner_mode=MODE_RESTRICTED_TOKEN,
        skill_dir=str(skill_dir),
    )


@pytest.fixture
def runner() -> WindowsSandboxRunner:
    return WindowsSandboxRunner(default_timeout=30.0)


class _FakeAclPlan:
    """Stands in for a real AclPlan so we can observe apply/rollback."""

    def __init__(self, dry_run, restore_notes=None, restore_raises=None):
        self.dry_run = dry_run
        self.enforced = not dry_run
        self.restored = 0
        self._restore_notes = restore_notes or []
        self._restore_raises = restore_raises

    def describe(self):
        return {
            "target": "<fake>",
            "dry_run": self.dry_run,
            "enforced": self.enforced,
            "entries": [],
            "warnings": [],
        }

    def restore(self):
        self.restored += 1
        if self._restore_raises is not None:
            raise self._restore_raises
        return list(self._restore_notes)


def _install_profile(monkeypatch, acl_mode, account_sid="S-1-5-32-544"):
    """Force a resolved profile so the test does not depend on host env."""
    from app.core.skill_engine import sandbox_profile as sp

    profile = sp.SandboxProfile(
        job_object_enabled=True,
        job_active_process_limit=None,
        sandbox_account=None,
        sandbox_account_sid=account_sid,
        acl_mode=acl_mode,
        network_boundary_mode="disabled",
        profile_mode="hardened",
        blocking_errors=[],
        warnings=[],
    )
    monkeypatch.setattr(ws, "load_profile", lambda: profile)
    return profile


# ==============================================================================
# acl_mode="enforce" must be reachable at all
# ==============================================================================

def test_enforce_profile_is_not_a_blocking_error(monkeypatch):
    """Regression: enforce used to be rejected by the profile gate."""
    from app.core.skill_engine import sandbox_profile as sp

    monkeypatch.setenv(sp.ENV_ACL_MODE, sp.MODE_ENFORCE)
    monkeypatch.setenv(sp.ENV_SANDBOX_ACCOUNT_SID, "S-1-5-32-544")
    profile = sp.load_profile()
    assert profile.acl_mode == sp.MODE_ENFORCE
    assert profile.blocking_errors == []
    assert profile.require() is profile


def test_enforce_warning_does_not_say_no_acl_is_written(monkeypatch):
    from app.core.skill_engine import sandbox_profile as sp

    monkeypatch.setenv(sp.ENV_ACL_MODE, sp.MODE_ENFORCE)
    monkeypatch.setenv(sp.ENV_SANDBOX_ACCOUNT_SID, "S-1-5-32-544")
    joined = " ".join(sp.load_profile().warnings).lower()
    assert "no acl is written" not in joined
    assert "no acl" not in joined


# ==============================================================================
# dry_run is wired from the profile mode
# ==============================================================================

def test_plan_mode_builds_a_dry_run_plan(runner, echo_skill, monkeypatch):
    _install_profile(monkeypatch, "dry_run")
    seen = {}

    def _capture(target, principal, caps, dry_run=True):
        seen["dry_run"] = dry_run
        return _FakeAclPlan(dry_run=dry_run)

    monkeypatch.setattr(ws, "build_acl_plan", _capture)
    monkeypatch.setattr(
        runner, "_spawn_restricted_token_subprocess",
        lambda **kw: _ok_result(kw),
    )
    runner.run_skill_sync(echo_skill, {"hello": "world"})
    assert seen["dry_run"] is True


def test_enforce_mode_builds_an_enforcing_plan(runner, echo_skill, monkeypatch):
    _install_profile(monkeypatch, "enforce")
    seen = {}

    def _capture(target, principal, caps, dry_run=True):
        seen["dry_run"] = dry_run
        return _FakeAclPlan(dry_run=dry_run)

    monkeypatch.setattr(ws, "build_acl_plan", _capture)
    monkeypatch.setattr(
        runner, "_spawn_restricted_token_subprocess",
        lambda **kw: _ok_result(kw),
    )
    result = runner.run_skill_sync(echo_skill, {"hello": "world"})
    assert seen["dry_run"] is False
    assert result.acl_plan["enforced"] is True


def test_disabled_mode_builds_no_plan_at_all(runner, echo_skill, monkeypatch):
    _install_profile(monkeypatch, "disabled")

    def _boom(*a, **k):
        raise AssertionError("build_acl_plan must not be called when disabled")

    monkeypatch.setattr(ws, "build_acl_plan", _boom)
    monkeypatch.setattr(
        runner, "_spawn_restricted_token_subprocess",
        lambda **kw: _ok_result(kw),
    )
    result = runner.run_skill_sync(echo_skill, {"hello": "world"})
    assert result.acl_plan is None


# ==============================================================================
# fail-closed: an ACL failure must not start a child
# ==============================================================================

def test_acl_plan_failure_does_not_start_a_child(runner, echo_skill, monkeypatch):
    from app.core.skill_engine.acl_guard import AclPlanError

    _install_profile(monkeypatch, "enforce")

    def _boom(*a, **k):
        raise AclPlanError("malformed principal")

    monkeypatch.setattr(ws, "build_acl_plan", _boom)

    def _must_not_run(**kw):
        raise AssertionError("no child may be started after an ACL failure")

    monkeypatch.setattr(runner, "_spawn_restricted_token_subprocess", _must_not_run)
    result = runner.run_skill_sync(echo_skill, {"hello": "world"})
    assert result.success is False
    assert result.sandbox_enforced is False
    assert "malformed principal" in result.error


# ==============================================================================
# rollback
# ==============================================================================

def test_acl_is_restored_after_a_successful_run(runner, echo_skill, monkeypatch):
    _install_profile(monkeypatch, "enforce")
    plan = _FakeAclPlan(dry_run=False)
    monkeypatch.setattr(ws, "build_acl_plan", lambda *a, **k: plan)
    monkeypatch.setattr(
        runner, "_spawn_restricted_token_subprocess",
        lambda **kw: _ok_result(kw),
    )
    runner.run_skill_sync(echo_skill, {"hello": "world"})
    assert plan.restored == 1


def test_acl_is_restored_after_a_failing_child(runner, tmp_path, monkeypatch):
    skill_dir = tmp_path / "boom_skill"
    skill_dir.mkdir()
    (skill_dir / "main.py").write_text(BOOM_SKILL, encoding="utf-8")
    skill = SkillDefinition(
        name="boom_skill",
        description="Exits non-zero.",
        entrypoint="main.py",
        runner_mode=MODE_RESTRICTED_TOKEN,
        skill_dir=str(skill_dir),
    )
    _install_profile(monkeypatch, "enforce")
    plan = _FakeAclPlan(dry_run=False)
    monkeypatch.setattr(ws, "build_acl_plan", lambda *a, **k: plan)
    monkeypatch.setattr(
        runner, "_spawn_restricted_token_subprocess",
        lambda **kw: _fail_result(kw),
    )
    runner.run_skill_sync(skill, {"hello": "world"})
    assert plan.restored == 1


def test_acl_is_restored_when_the_child_cannot_be_spawned(
    runner, echo_skill, monkeypatch
):
    _install_profile(monkeypatch, "enforce")
    plan = _FakeAclPlan(dry_run=False)
    monkeypatch.setattr(ws, "build_acl_plan", lambda *a, **k: plan)

    def _raise(**kw):
        raise OSError("CreateProcessAsUserW failed")

    monkeypatch.setattr(runner, "_spawn_restricted_token_subprocess", _raise)
    with pytest.raises(OSError):
        runner.run_skill_sync(echo_skill, {"hello": "world"})
    assert plan.restored == 1


def test_rollback_failure_is_reported_on_stderr_not_swallowed(
    runner, echo_skill, monkeypatch, capsys
):
    _install_profile(monkeypatch, "enforce")
    plan = _FakeAclPlan(dry_run=False, restore_raises=RuntimeError("denied"))
    monkeypatch.setattr(ws, "build_acl_plan", lambda *a, **k: plan)
    monkeypatch.setattr(
        runner, "_spawn_restricted_token_subprocess",
        lambda **kw: _ok_result(kw),
    )
    runner.run_skill_sync(echo_skill, {"hello": "world"})
    assert plan.restored == 1
    assert "rollback" in capsys.readouterr().err.lower()


def test_rollback_notes_are_written_to_stderr(
    runner, echo_skill, monkeypatch, capsys
):
    _install_profile(monkeypatch, "enforce")
    plan = _FakeAclPlan(
        dry_run=False,
        restore_notes=["NTFS ACL rollback FAILED: access denied."],
    )
    monkeypatch.setattr(ws, "build_acl_plan", lambda *a, **k: plan)
    monkeypatch.setattr(
        runner, "_spawn_restricted_token_subprocess",
        lambda **kw: _ok_result(kw),
    )
    runner.run_skill_sync(echo_skill, {"hello": "world"})
    assert "rollback FAILED" in capsys.readouterr().err


# ==============================================================================
# honesty: the ACL layer must not be reported as sandbox_enforced
# ==============================================================================

def test_acl_enforcement_alone_does_not_set_sandbox_enforced(
    runner, echo_skill, monkeypatch
):
    _install_profile(monkeypatch, "enforce")
    monkeypatch.setattr(
        ws, "build_acl_plan",
        lambda *a, **k: _FakeAclPlan(dry_run=False),
    )

    def _unavailable(**kw):
        res = _ok_result(kw)
        res.sandbox_enforced = False
        res.runner_mode = ws.EFFECTIVE_MODE_RESTRICTED_TOKEN_UNAVAILABLE
        return res

    monkeypatch.setattr(
        runner, "_spawn_restricted_token_subprocess", _unavailable
    )
    result = runner.run_skill_sync(echo_skill, {"hello": "world"})
    assert result.acl_plan["enforced"] is True
    assert result.sandbox_enforced is False


def _ok_result(kw):
    from app.core.skill_engine.windows_sandbox import SandboxExecutionResult

    return SandboxExecutionResult(
        success=True,
        stdout='{"success": true}',
        stderr="",
        returncode=0,
        runner_mode=ws.EFFECTIVE_MODE_RESTRICTED_TOKEN,
        requested_runner_mode=ws.MODE_RESTRICTED_TOKEN,
        sandbox_enforced=True,
    )


def _fail_result(kw):
    from app.core.skill_engine.windows_sandbox import SandboxExecutionResult

    return SandboxExecutionResult(
        success=False,
        stdout="",
        stderr="boom",
        returncode=3,
        runner_mode=ws.EFFECTIVE_MODE_RESTRICTED_TOKEN,
        requested_runner_mode=ws.MODE_RESTRICTED_TOKEN,
        sandbox_enforced=True,
    )

