# -*- coding: utf-8 -*-
"""Tests for the declarative sandbox hardening profile.

The profile is a configuration/policy layer. These tests pin the honest
posture: Job Object containment is on by default and cannot be switched off,
while the administrator-only layers (sandbox account, NTFS ACL, OS network
boundary) either plan or fail closed -- they never claim enforcement.
"""
from pathlib import Path
import sys

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest

from app.core.skill_engine.sandbox_profile import (
    ENV_ACL_MODE,
    ENV_JOB_ACTIVE_PROCESS_LIMIT,
    ENV_JOB_OBJECT_ENABLED,
    ENV_OS_NETWORK_BOUNDARY,
    ENV_SANDBOX_ACCOUNT,
    ENV_SANDBOX_ACCOUNT_SID,
    MODE_DISABLED,
    MODE_DRY_RUN,
    MODE_ENFORCE,
    SandboxProfileError,
    load_profile,
)

_ALL_ENV = [
    ENV_ACL_MODE,
    ENV_JOB_ACTIVE_PROCESS_LIMIT,
    ENV_JOB_OBJECT_ENABLED,
    ENV_OS_NETWORK_BOUNDARY,
    ENV_SANDBOX_ACCOUNT,
    ENV_SANDBOX_ACCOUNT_SID,
    "COG_SKILL_SANDBOX_PROFILE_MODE",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ALL_ENV:
        monkeypatch.delenv(name, raising=False)


# --- Job Object: implemented and not optional -------------------------------

def test_job_object_is_enabled_by_default():
    profile = load_profile()
    assert profile.job_object_enabled is True
    assert profile.ok, profile.blocking_errors


@pytest.mark.parametrize("raw", ["0", "false", "no", "off"])
def test_job_object_cannot_be_disabled(monkeypatch, raw):
    # The restricted-token path always contains the child in a job. Recording
    # the operator request is fine; honouring it would uncontain the child.
    monkeypatch.setenv(ENV_JOB_OBJECT_ENABLED, raw)
    profile = load_profile()
    assert profile.job_object_enabled is True
    assert any("Job" in w for w in profile.warnings)


def test_non_boolean_job_flag_assumes_enabled(monkeypatch):
    monkeypatch.setenv(ENV_JOB_OBJECT_ENABLED, "maybe")
    profile = load_profile()
    assert profile.job_object_enabled is True
    assert any("not a boolean" in w for w in profile.warnings)


# --- Job Object active process cap -----------------------------------------

def test_active_process_limit_is_honoured(monkeypatch):
    monkeypatch.setenv(ENV_JOB_ACTIVE_PROCESS_LIMIT, "4")
    assert load_profile().job_active_process_limit == 4


@pytest.mark.parametrize("raw", ["0", "1", "-3"])
def test_too_small_active_process_limit_is_dropped(monkeypatch, raw):
    monkeypatch.setenv(ENV_JOB_ACTIVE_PROCESS_LIMIT, raw)
    profile = load_profile()
    assert profile.job_active_process_limit is None
    assert any("minimum of 2" in w for w in profile.warnings)


def test_non_integer_active_process_limit_is_dropped(monkeypatch):
    monkeypatch.setenv(ENV_JOB_ACTIVE_PROCESS_LIMIT, "many")
    profile = load_profile()
    assert profile.job_active_process_limit is None
    assert any("not an integer" in w for w in profile.warnings)


def test_absent_active_process_limit_means_no_cap_not_no_job():
    # None must not be read downstream as "skip the job object".
    profile = load_profile()
    assert profile.job_active_process_limit is None
    assert profile.job_object_enabled is True


# --- NTFS ACL layer: planning only -----------------------------------------

def test_acl_disabled_by_default_does_not_block():
    profile = load_profile()
    assert profile.acl_mode == MODE_DISABLED
    assert profile.ok


def test_acl_without_principal_fails_closed(monkeypatch):
    monkeypatch.setenv(ENV_ACL_MODE, MODE_DRY_RUN)
    profile = load_profile()
    assert not profile.ok
    assert any(ENV_SANDBOX_ACCOUNT in e for e in profile.blocking_errors)
    with pytest.raises(SandboxProfileError):
        profile.require()


def test_acl_dry_run_is_planning_only(monkeypatch):
    """dry_run stays planning-only: no ACE is written."""
    monkeypatch.setenv(ENV_ACL_MODE, MODE_DRY_RUN)
    monkeypatch.setenv(ENV_SANDBOX_ACCOUNT_SID, "S-1-5-21-1-2-3-1001")
    profile = load_profile().require()
    assert profile.acl_mode == MODE_DRY_RUN
    assert profile.describe()["acl_enforced"] is False
    assert any("plan only" in w for w in profile.warnings)
    assert any("no ACL is written" in w for w in profile.warnings)


def test_acl_enforce_is_reachable_and_warns_scoped(monkeypatch):
    """enforce is real on Windows, so it must NOT be a blocking error.

    It writes a scoped allow ACE to the per-execution workspace, verifies by
    read-back, and restores best-effort -- but it is still not a container.
    """
    monkeypatch.setenv(ENV_ACL_MODE, MODE_ENFORCE)
    monkeypatch.setenv(ENV_SANDBOX_ACCOUNT_SID, "S-1-5-21-1-2-3-1001")
    profile = load_profile().require()
    assert profile.acl_mode == MODE_ENFORCE
    assert profile.describe()["acl_enforced"] is False  # never claimed statically
    enforce_warnings = [w for w in profile.warnings if "scoped allow ACE" in w]
    assert enforce_warnings, profile.warnings
    text = " ".join(enforce_warnings)
    assert "read back for verification" in text
    assert "restored best-effort" in text
    assert "NOT a container" in text
    # Must not still claim the enforce path is unimplemented.
    assert not any("NOT implemented" in w for w in profile.warnings)


def test_account_name_without_sid_warns(monkeypatch):
    monkeypatch.setenv(ENV_ACL_MODE, MODE_DRY_RUN)
    monkeypatch.setenv(ENV_SANDBOX_ACCOUNT_SID, "S-1-5-21-1-2-3-1001")
    monkeypatch.setenv(ENV_SANDBOX_ACCOUNT, "cog-skill-sandbox")
    profile = load_profile().require()
    assert profile.sandbox_account == "cog-skill-sandbox"
    assert profile.describe()["sandbox_account_created"] is False


# --- OS network boundary: planning only ------------------------------------

def test_network_disabled_by_default_does_not_block():
    profile = load_profile()
    assert profile.network_boundary_mode == MODE_DISABLED
    assert profile.ok


def test_network_enforce_fails_closed(monkeypatch):
    monkeypatch.setenv(ENV_OS_NETWORK_BOUNDARY, MODE_ENFORCE)
    profile = load_profile()
    assert not profile.ok
    assert any("Firewall" in e for e in profile.blocking_errors)


def test_network_dry_run_is_planning_only(monkeypatch):
    monkeypatch.setenv(ENV_OS_NETWORK_BOUNDARY, MODE_DRY_RUN)
    profile = load_profile().require()
    assert profile.describe()["network_boundary_enforced"] is False
    assert any("only" in w and "policy" in w for w in profile.warnings)


def test_unknown_mode_is_recorded_not_silently_accepted(monkeypatch):
    monkeypatch.setenv(ENV_ACL_MODE, "sideways")
    profile = load_profile()
    assert any("is not one of" in w for w in profile.warnings)
    assert profile.acl_mode == MODE_DISABLED


# --- describe() must never overstate ---------------------------------------

def test_describe_never_claims_enforcement():
    described = load_profile().describe()
    assert described["sandbox_account_created"] is False
    assert described["acl_enforced"] is False
    assert described["network_boundary_enforced"] is False
