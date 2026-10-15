"""Sandbox profile: declarative hardening configuration for skill runs.

WHAT THIS MODULE ACTUALLY DOES
------------------------------
This module is a **policy / configuration layer**. It answers one question:
"which hardening measures did the operator ask for, and are we allowed to
act on them?" It creates no Windows user account and installs no firewall
rule. It does not itself write ACLs -- the runner does that in
:mod:`app.core.skill_engine.acl_guard` when the operator selects
``acl_mode="enforce"``.

The default posture is ``dry_run``. Administrator-only measures are opt-in via
environment variables and are **never** auto-elevated: if ``enforce`` is
requested but the prerequisites are missing, :func:`load_profile` reports a
blocking error instead of trying to acquire privileges.

MEASURE STATUS (honest)
-----------------------
* Job Object -- **Implemented**. ``job_object_enabled`` is honoured for real by
  :mod:`app.core.skill_engine.restricted_token`; containment cannot be turned
  off on the restricted-token path.
* Sandbox account -- **Not implemented**. Only the name/SID are *declared*
  here; no account is created and no logon token is produced.
* NTFS ACL -- **Partial**. ``dry_run`` only computes a plan; ``enforce``
  really writes a scoped allow ACE set to the per-execution workspace via
  :mod:`app.core.skill_engine.acl_guard` (``SetNamedSecurityInfoW``),
  verifies it by read-back, and restores it best-effort afterwards.
  Parent-directory deny ACEs, a dedicated sandbox account, and crash-recovery
  cleanup are still absent, and a hard runner kill can leave the ACEs behind.
* OS network boundary -- **Partial**. Only a plan is computed
  (:mod:`app.core.skill_engine.os_network_boundary`); no firewall rule exists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

# --- Modes -----------------------------------------------------------------
MODE_DISABLED = "disabled"
MODE_DRY_RUN = "dry_run"
MODE_ENFORCE = "enforce"
_VALID_MODES = (MODE_DISABLED, MODE_DRY_RUN, MODE_ENFORCE)

# --- Environment variables (all optional; defaults are the safe posture) ----
ENV_PROFILE_MODE = "COG_SKILL_SANDBOX_PROFILE_MODE"
ENV_SANDBOX_ACCOUNT = "COG_SKILL_SANDBOX_ACCOUNT"
ENV_SANDBOX_ACCOUNT_SID = "COG_SKILL_SANDBOX_ACCOUNT_SID"
ENV_JOB_OBJECT_ENABLED = "COG_SKILL_JOB_OBJECT_ENABLED"
ENV_JOB_ACTIVE_PROCESS_LIMIT = "COG_SKILL_JOB_ACTIVE_PROCESS_LIMIT"
ENV_ACL_MODE = "COG_SKILL_ACL_MODE"
ENV_OS_NETWORK_BOUNDARY = "COG_SKILL_OS_NETWORK_BOUNDARY"

_TRUTHY = {"1", "true", "yes", "on"}


class SandboxProfileError(ValueError):
    """Raised when a profile is requested that cannot be honoured safely."""


@dataclass
class SandboxProfile:
    """Resolved hardening configuration for a skill run."""

    # --- Implemented ---
    job_object_enabled: bool = True
    job_active_process_limit: Optional[int] = None

    # --- Declared only; not created / not enforced ---
    sandbox_account: Optional[str] = None
    sandbox_account_sid: Optional[str] = None
    acl_mode: str = MODE_DISABLED
    network_boundary_mode: str = MODE_DISABLED
    profile_mode: str = MODE_DRY_RUN

    # If non-empty the run must not start. Used to fail closed.
    blocking_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocking_errors

    def require(self) -> "SandboxProfile":
        """Raise if the profile cannot be honoured. Fails closed."""
        if self.blocking_errors:
            raise SandboxProfileError(
                "Sandbox profile cannot be satisfied: "
                + " ".join(self.blocking_errors)
            )
        return self

    def describe(self) -> dict:
        return {
            "job_object_enabled": self.job_object_enabled,
            "job_active_process_limit": self.job_active_process_limit,
            "sandbox_account_declared": bool(self.sandbox_account),
            "sandbox_account_sid_declared": bool(self.sandbox_account_sid),
            "sandbox_account_created": False,
            "acl_mode": self.acl_mode,
            "acl_enforced": False,
            "network_boundary_mode": self.network_boundary_mode,
            "network_boundary_enforced": False,
            "profile_mode": self.profile_mode,
            "blocking_errors": list(self.blocking_errors),
            "warnings": list(self.warnings),
        }


def _mode_from_env(var: str, default: str, warnings: List[str]) -> str:
    raw = os.environ.get(var, "").strip().lower()
    if not raw:
        return default
    if raw not in _VALID_MODES:
        warnings.append(
            f"{var}={raw!r} is not one of {list(_VALID_MODES)}; falling back to "
            f"{default!r}. No enforcement was attempted."
        )
        return default
    return raw


def _parse_limit(raw: str, warnings: List[str]) -> Optional[int]:
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        warnings.append(
            f"{ENV_JOB_ACTIVE_PROCESS_LIMIT}={raw!r} is not an integer; the job "
            "will be created without an active-process cap."
        )
        return None
    if value < 2:
        warnings.append(
            f"{ENV_JOB_ACTIVE_PROCESS_LIMIT}={value} is below the minimum of 2; "
            "the job will be created without an active-process cap."
        )
        return None
    return value


def load_profile() -> SandboxProfile:
    """Build the effective :class:`SandboxProfile` from the environment.

    Never raises for configuration the operator merely *requested*; unmet
    requests land in ``blocking_errors`` so the runner can refuse to start.
    """
    warnings: List[str] = []
    errors: List[str] = []

    profile_mode = _mode_from_env(ENV_PROFILE_MODE, MODE_DRY_RUN, warnings)
    acl_mode = _mode_from_env(ENV_ACL_MODE, MODE_DISABLED, warnings)
    network_mode = _mode_from_env(
        ENV_OS_NETWORK_BOUNDARY, MODE_DISABLED, warnings
    )

    raw_job = os.environ.get(ENV_JOB_OBJECT_ENABLED, "").strip().lower()
    job_enabled = raw_job not in _FALSEY if raw_job else True
    if raw_job and raw_job not in _TRUTHY and raw_job not in _FALSEY:
        warnings.append(
            f"{ENV_JOB_OBJECT_ENABLED}={raw_job!r} is not a boolean; assuming "
            "enabled."
        )
        job_enabled = True

    account = os.environ.get(ENV_SANDBOX_ACCOUNT, "").strip() or None
    account_sid = os.environ.get(ENV_SANDBOX_ACCOUNT_SID, "").strip() or None
    if acl_mode != MODE_DISABLED and not account and not account_sid:
        errors.append(
            f"An NTFS ACL plan was requested (mode {acl_mode!r}) but neither "
            f"{ENV_SANDBOX_ACCOUNT} nor {ENV_SANDBOX_ACCOUNT_SID} is set, so no "
            "principal could be granted or denied access. Refusing to guess an "
            "identity."
        )
    if account and not account_sid:
        warnings.append(
            f"{ENV_SANDBOX_ACCOUNT} is set without {ENV_SANDBOX_ACCOUNT_SID}. "
            "The SID is what an ACL entry needs; no SID resolution is performed "
            "by this build."
        )

    # NTFS ACL enforcement IS implemented on Windows via SetNamedSecurityInfoW
    # with a read-back verification step, so acl_mode="enforce" is not a
    # blocking error. Non-Windows hosts fail closed at ACL-build time instead.
    if network_mode == MODE_ENFORCE:
        errors.append(
            "An OS-level network boundary is NOT implemented. No Windows "
            "Firewall rule is created by this build; use 'dry_run' to inspect "
            "the intended policy."
        )

    profile = SandboxProfile(
        job_object_enabled=job_enabled,
        job_active_process_limit=_parse_limit(
            os.environ.get(ENV_JOB_ACTIVE_PROCESS_LIMIT, ""), warnings
        ),
        sandbox_account=account,
        sandbox_account_sid=account_sid,
        acl_mode=acl_mode,
        network_boundary_mode=network_mode,
        profile_mode=profile_mode,
        blocking_errors=errors,
        warnings=warnings,
    )

    if not job_enabled:
        warnings.append(
            f"{ENV_JOB_OBJECT_ENABLED} requested Job Object containment to be "
            "disabled. Job containment cannot be turned off on the "
            "restricted-token path; the request is recorded but the job is "
            "still created."
        )
        profile.job_object_enabled = True

    if acl_mode == MODE_ENFORCE:
        warnings.append(
            "NTFS ACL mode is 'enforce': a scoped allow ACE is written to the "
            "per-execution workspace, read back for verification, and restored "
            "best-effort when the run ends. This is per-workspace NTFS hardening "
            "only -- it is NOT a container, and it does not remove the host "
            "account's own access to the workspace."
        )
    elif acl_mode != MODE_DISABLED:
        warnings.append(
            f"NTFS ACL mode is {acl_mode!r}: plan only, no ACL is written. The "
            "skill still sees the full NTFS permissions of its host account."
        )
    if network_mode != MODE_DISABLED:
        warnings.append(
            f"OS network boundary mode is {network_mode!r}: this build only "
            "computes a policy. No firewall rule exists, so egress is bounded "
            "only by the in-process Python guard."
        )

    return profile


_FALSEY = {"0", "false", "no", "off"}

__all__ = [
    "ENV_ACL_MODE",
    "ENV_JOB_ACTIVE_PROCESS_LIMIT",
    "ENV_JOB_OBJECT_ENABLED",
    "ENV_OS_NETWORK_BOUNDARY",
    "ENV_PROFILE_MODE",
    "ENV_SANDBOX_ACCOUNT",
    "ENV_SANDBOX_ACCOUNT_SID",
    "MODE_DISABLED",
    "MODE_DRY_RUN",
    "MODE_ENFORCE",
    "SandboxProfile",
    "SandboxProfileError",
    "load_profile",
]
