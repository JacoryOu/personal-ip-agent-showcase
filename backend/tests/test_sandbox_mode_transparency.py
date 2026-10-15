# -*- coding: utf-8 -*-
"""Tests that the skill runner never overstates the isolation it actually applies.

As of the ``codex/skill-restricted-token`` work:

* ``restricted_token`` really does create a Windows Restricted Token via
  ``CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)`` and launch the skill with
  ``CreateProcessAsUserW``. On success the runner reports
  ``runner_mode="restricted_token"`` and ``sandbox_enforced=True``.
* If the token cannot be created or attached, the runner **fails closed**:
  the skill is never started and ``sandbox_enforced`` stays ``False``.
* ``wsb`` still fails closed -- ``WindowsSandbox.exe`` is never launched.

What a restricted token still does *not* provide (AppContainer, filesystem ACL
isolation, network restriction, Windows Sandbox virtualization, enforcement of
SKILL.md ``permissions`` metadata) is asserted in the scope-warning tests, so a
future change cannot quietly start overstating the guarantee.
"""
from pathlib import Path
import sys

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import json

import pytest

from app.core.skill_engine.discovery import SkillDefinition
from app.core.skill_engine.windows_sandbox import (
    EFFECTIVE_MODE_RESTRICTED_TOKEN,
    EFFECTIVE_MODE_RESTRICTED_TOKEN_UNAVAILABLE,
    EFFECTIVE_MODE_SANITIZED_SUBPROCESS,
    EFFECTIVE_MODE_WSB_UNSUPPORTED,
    MODE_RESTRICTED_TOKEN,
    MODE_WSB,
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


# ==============================================================================
# restricted_token: a real restricted token, honestly reported
# ==============================================================================

def test_restricted_token_reports_actual_effective_mode(runner, echo_skill):
    result = runner.run_skill_sync(echo_skill, {"hello": "world"}, runner_mode=MODE_RESTRICTED_TOKEN)

    assert result.success is True, result.error
    assert result.requested_runner_mode == MODE_RESTRICTED_TOKEN
    assert result.runner_mode == EFFECTIVE_MODE_RESTRICTED_TOKEN
    assert result.sandbox_enforced is True


def test_restricted_token_scope_warning_does_not_overstate(runner, echo_skill):
    """A successful run must spell out what a restricted token is NOT."""
    result = runner.run_skill_sync(echo_skill, {}, runner_mode=MODE_RESTRICTED_TOKEN)

    assert result.sandbox_enforced is True
    assert result.warnings, "a scope warning must always be surfaced"
    warning = " ".join(result.warnings).lower()
    assert "does not mean" in warning or "not mean" in warning
    for unimplemented in ("appcontainer", "network", "acl", "windows sandbox"):
        assert unimplemented in warning, f"scope warning must disclose: {unimplemented}"


def test_restricted_token_still_executes_and_parses_json(runner, echo_skill):
    result = runner.run_skill_sync(echo_skill, {"n": 7}, runner_mode=MODE_RESTRICTED_TOKEN)

    assert result.success is True
    assert isinstance(result.output, dict)
    assert result.output["echo"] == {"n": 7}


def test_restricted_token_fails_closed_when_token_unavailable(
    runner, echo_skill, monkeypatch
):
    """If the Win32 token path breaks, the skill must NOT run unsandboxed."""
    def _boom(*args, **kwargs):
        from app.core.skill_engine.restricted_token import RestrictedTokenError

        raise RestrictedTokenError("simulated token creation failure")

    monkeypatch.setattr(
        "app.core.skill_engine.windows_sandbox.create_restricted_token", _boom
    )

    spawned = []
    monkeypatch.setattr(
        runner,
        "_spawn_sanitized_subprocess",
        lambda *a, **k: spawned.append(a) or pytest.fail(
            "must not fall back to an unsandboxed subprocess"
        ),
    )

    result = runner.run_skill_sync(echo_skill, {}, runner_mode=MODE_RESTRICTED_TOKEN)

    assert spawned == []
    assert result.success is False
    assert result.sandbox_enforced is False
    assert result.runner_mode == EFFECTIVE_MODE_RESTRICTED_TOKEN_UNAVAILABLE
    assert result.returncode == -1
    warning = " ".join(result.warnings).lower()
    assert "not executed" in warning or "failing closed" in warning


def test_missing_entrypoint_is_reported_with_honest_mode(runner, echo_skill):
    result = runner.run_skill_sync(echo_skill, {}, runner_mode=MODE_RESTRICTED_TOKEN)
    assert result.success is True

    broken = echo_skill.model_copy(update={"entrypoint": "does_not_exist.py"})
    result = runner.run_skill_sync(broken, {}, runner_mode=MODE_RESTRICTED_TOKEN)

    assert result.success is False
    assert "not found" in (result.error or "")
    # Nothing was launched, so nothing was enforced.
    assert result.sandbox_enforced is False


# ==============================================================================
# wsb: fail closed, never execute
# ==============================================================================

def test_wsb_fails_closed_with_explicit_error(runner, echo_skill):
    result = runner.run_skill_sync(echo_skill, {}, runner_mode=MODE_WSB)

    assert result.success is False
    assert result.runner_mode == EFFECTIVE_MODE_WSB_UNSUPPORTED
    assert result.requested_runner_mode == MODE_WSB
    assert result.sandbox_enforced is False
    assert result.returncode == -1

    error = (result.error or "").lower()
    assert "windowssandbox.exe" in error
    assert "not implemented" in error


def test_wsb_never_spawns_a_process(runner, echo_skill, monkeypatch):
    calls = []

    def _boom(*args, **kwargs):
        calls.append(args)
        raise AssertionError("no process may be started for wsb mode")

    monkeypatch.setattr(runner, "_spawn_sanitized_subprocess", _boom)
    monkeypatch.setattr(
        runner,
        "_spawn_restricted_token_subprocess",
        _boom,
        raising=False,
    )

    result = runner.run_skill_sync(echo_skill, {}, runner_mode=MODE_WSB)

    assert result.success is False
    assert calls == [], "no subprocess should be started for wsb mode"
    assert result.wsb_config_path is None


def test_wsb_config_generator_is_not_executed(runner, echo_skill, monkeypatch):
    """The .wsb generator stays available for diagnostics but is not on the hot path."""
    monkeypatch.setattr(
        runner,
        "_spawn_sanitized_subprocess",
        lambda *a, **k: pytest.fail("must not execute under wsb"),
    )
    monkeypatch.setattr(
        runner,
        "_spawn_restricted_token_subprocess",
        lambda *a, **k: pytest.fail("must not execute under wsb"),
        raising=False,
    )
    result = runner.run_skill_sync(echo_skill, {}, runner_mode=MODE_WSB)
    assert result.success is False


# ==============================================================================
# unknown modes
# ==============================================================================

def test_unknown_mode_fails_closed(runner, echo_skill):
    result = runner.run_skill_sync(echo_skill, {}, runner_mode="docker")

    assert result.success is False
    assert result.requested_runner_mode == "docker"
    assert "unknown runner_mode" in (result.error or "").lower()


def test_skill_level_default_mode_is_used(runner, echo_skill):
    wsb_skill = echo_skill.model_copy(update={"runner_mode": MODE_WSB})
    result = runner.run_skill_sync(wsb_skill, {}, runner_mode=None)
    assert result.success is False
    assert result.requested_runner_mode == MODE_WSB


# ==============================================================================
# environment sanitization / timeouts must not regress
# ==============================================================================

def test_sanitized_env_strips_secrets(monkeypatch):
    monkeypatch.setenv("MY_SECRET_TOKEN", "leak")
    monkeypatch.setenv("OPENAI_API_KEY", "leak")
    monkeypatch.setenv("SYSTEMROOT", r"C:\Windows")

    env = WindowsSandboxRunner().build_sanitized_env()

    assert "MY_SECRET_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert env["SYSTEMROOT"] == r"C:\Windows"


def test_timeout_is_reported_with_honest_mode(tmp_path):
    skill_dir = tmp_path / "slow_skill"
    skill_dir.mkdir()
    (skill_dir / "main.py").write_text(
        "import time\ntime.sleep(30)\n", encoding="utf-8"
    )
    skill = SkillDefinition(
        name="slow_skill",
        description="Sleeps forever.",
        entrypoint="main.py",
        runner_mode=MODE_RESTRICTED_TOKEN,
        skill_dir=str(skill_dir),
    )

    result = WindowsSandboxRunner(default_timeout=1.0).run_skill_sync(
        skill, {}, runner_mode=MODE_RESTRICTED_TOKEN
    )

    assert result.success is False
    assert result.timed_out is True
    assert result.runner_mode == EFFECTIVE_MODE_RESTRICTED_TOKEN
    assert result.sandbox_enforced is True
