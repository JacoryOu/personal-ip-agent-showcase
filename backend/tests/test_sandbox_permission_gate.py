# -*- coding: utf-8 -*-
"""Regression tests for the SKILL.md permissions *pre-launch* gate.

The gate is only worth having if it fires **before** anything is created. These
tests monkeypatch the three things that must never run on a denial:

* ``tempfile.mkdtemp`` -- the per-execution workspace
* ``run_process_with_restricted_token`` -- the restricted token itself
* ``WindowsSandboxRunner._spawn_restricted_token_subprocess`` -- the child

If any of them is called after a deny, the isolation story would be false: a
denied skill would still touch the filesystem, mint a token, or start a
process.
"""
from pathlib import Path
import sys

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import tempfile

import pytest

from app.core.skill_engine import windows_sandbox as ws_module
from app.core.skill_engine.discovery import SkillDefinition
from app.core.skill_engine.policy import (
    Decision,
    NetworkPolicy,
    SkillPermissionPolicy,
)
from app.core.skill_engine.windows_sandbox import (
    MODE_RESTRICTED_TOKEN,
    MODE_WSB,
    WindowsSandboxRunner,
)


SKILL_SOURCE = """
print("this skill must never execute")
"""


def _write_skill(tmp_path, permissions, mode=MODE_RESTRICTED_TOKEN, name="gated_skill"):
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "main.py").write_text(SKILL_SOURCE, encoding="utf-8")
    return SkillDefinition(
        name=name,
        description="skill used to prove the deny path runs nothing",
        entrypoint="main.py",
        runner_mode=mode,
        skill_dir=str(skill_dir),
        permissions=permissions,
    )


@pytest.fixture
def tripwire(monkeypatch):
    """Make every side effect of a real execution fail loudly."""
    calls = {"mkdtemp": 0, "token": 0, "spawn": 0}

    def _boom_mkdtemp(*args, **kwargs):
        calls["mkdtemp"] += 1
        raise AssertionError("workspace created despite a permission denial")

    def _boom_token(*args, **kwargs):
        calls["token"] += 1
        raise AssertionError("restricted token created despite a permission denial")

    def _boom_spawn(self, *args, **kwargs):
        calls["spawn"] += 1
        raise AssertionError("child process spawned despite a permission denial")

    monkeypatch.setattr(ws_module.tempfile, "mkdtemp", _boom_mkdtemp)
    monkeypatch.setattr(
        ws_module, "run_process_with_restricted_token", _boom_token, raising=False
    )
    monkeypatch.setattr(
        ws_module.WindowsSandboxRunner, "_spawn_restricted_token_subprocess", _boom_spawn
    )
    return calls


def test_deny_creates_no_workspace_no_token_and_no_child(tmp_path, tripwire):
    skill = _write_skill(tmp_path, ["network:read"])
    runner = WindowsSandboxRunner(
        permission_policy=SkillPermissionPolicy(
            network_policy=NetworkPolicy(allow_hosts=[], allow_any_host=False)
        )
    )

    result = runner.run_skill_sync(skill, {})

    assert result.success is False
    assert result.policy_decision == Decision.DENY.value
    assert tripwire == {"mkdtemp": 0, "token": 0, "spawn": 0}


def test_deny_reports_the_denied_capability_and_reason(tmp_path, tripwire):
    skill = _write_skill(tmp_path, ["network:read"])
    runner = WindowsSandboxRunner(
        permission_policy=SkillPermissionPolicy(
            network_policy=NetworkPolicy(allow_hosts=[], allow_any_host=False)
        )
    )

    result = runner.run_skill_sync(skill, {})

    assert "network:read" in result.denied_capabilities
    assert result.policy_reasons
    assert result.sandbox_enforced is False
    assert "denied by permission policy" in (result.error or "")


def test_deny_does_not_claim_sandbox_enforcement(tmp_path, tripwire):
    skill = _write_skill(tmp_path, ["network:read"])
    runner = WindowsSandboxRunner(
        permission_policy=SkillPermissionPolicy(
            network_policy=NetworkPolicy(allow_hosts=[], allow_any_host=False)
        )
    )

    result = runner.run_skill_sync(skill, {})

    assert result.sandbox_enforced is False
    assert result.job_object_enforced is False
    assert result.returncode == -1


def test_unknown_runner_mode_still_fails_closed_without_side_effects(tmp_path, tripwire):
    """The gate must not become a bypass for unknown modes."""
    skill = _write_skill(tmp_path, [], mode="totally_unknown_mode")

    result = WindowsSandboxRunner().run_skill_sync(skill, {})

    assert result.success is False
    assert result.sandbox_enforced is False
    assert tripwire == {"mkdtemp": 0, "token": 0, "spawn": 0}


def test_wsb_mode_is_rejected_before_the_permission_gate(tmp_path, tripwire):
    skill = _write_skill(tmp_path, [], mode=MODE_WSB)

    result = WindowsSandboxRunner().run_skill_sync(skill, {}, runner_mode=MODE_WSB)

    assert result.success is False
    assert result.runner_mode == "wsb_unsupported"
    assert result.sandbox_enforced is False
    assert tripwire == {"mkdtemp": 0, "token": 0, "spawn": 0}
