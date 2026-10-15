"""Skill permission normalisation and pre-execution policy decisions.

HONESTY NOTE
------------
This module is the *single decision point* for SKILL.md ``permissions``
metadata, which used to be pure decoration: nothing read it before a skill
started. It answers one question -- may this skill run, in this execution
context, with these declared capabilities -- and returns an explicit
``allow`` / ``deny`` decision that the runner refuses to bypass.

What this layer genuinely enforces:

* A skill that declares **no** network capability is denied egress. The runner
  installs a runtime guard (see :mod:`app.core.skill_engine.network_guard`) that
  blocks every outbound connection for that child process.
* A skill that declares network capability runs only under the configured host
  allowlist, and a host outside that allowlist is blocked.
* A skill that requests a capability which is not authorised for the current
  execution context is denied the whole run -- the runner starts no process.
* Unattended (scheduled) execution never "asks a human". It either runs inside
  the pre-authorised unattended scope, or it is denied so the caller degrades.
  There is no interactive fallback on this path by design.

What this layer does NOT enforce: anything about a script's runtime behaviour
beyond the injected Python-level socket guard. It is a capability gate, not a
sandbox, and the host allowlist is only as strong as the configuration below.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Dict, FrozenSet, Iterable, List, Optional

from pydantic import BaseModel, Field

# Capability vocabulary. Anything unrecognised is preserved verbatim so that a
# typo can never silently widen a skill's permissions.
NETWORK_READ = "network:read"
NETWORK_WRITE = "network:write"
FS_READ = "filesystem:read"
FS_WRITE = "filesystem:write"
FS_ISOLATED = "filesystem:isolated"
EXEC = "exec"

# System-level allowlist of capabilities a scheduler/batch job may use.
# Comma or semicolon separated canonical capability names.
ENV_UNATTENDED_ALLOW_PERMISSIONS = "COG_SKILL_UNATTENDED_ALLOW_PERMISSIONS"

KNOWN_CAPABILITIES: FrozenSet[str] = frozenset(
    {NETWORK_READ, NETWORK_WRITE, FS_READ, FS_WRITE, FS_ISOLATED, EXEC}
)

NETWORK_CAPABILITIES: FrozenSet[str] = frozenset({NETWORK_READ, NETWORK_WRITE})

# Capabilities that reach outside the process. A restricted Windows token
# cannot stop any of these, which is exactly why they are policed here.
EXTERNAL_CAPABILITIES: FrozenSet[str] = frozenset(
    {NETWORK_READ, NETWORK_WRITE, FS_READ, FS_WRITE, EXEC}
)

WILDCARD_HOST = "*"

# Alias normalisation: SKILL.md authors write "network:read", "network_read",
# "Network Read", "network". All of those mean the same thing, and an
# unnormalised alias must never be read as "no permission declared".
_ALIASES: Dict[str, str] = {
    "network": NETWORK_READ,
    "net": NETWORK_READ,
    "network-read": NETWORK_READ,
    "network_read": NETWORK_READ,
    "network:outbound": NETWORK_READ,
    "network-outbound": NETWORK_READ,
    "http": NETWORK_READ,
    "https": NETWORK_READ,
    "network-write": NETWORK_WRITE,
    "network_write": NETWORK_WRITE,
    "network:publish": NETWORK_WRITE,
    "fs": FS_READ,
    "file": FS_READ,
    "files": FS_READ,
    "filesystem": FS_READ,
    "filesystem-read": FS_READ,
    "filesystem_read": FS_READ,
    "fs-write": FS_WRITE,
    "fs_write": FS_WRITE,
    "filesystem-write": FS_WRITE,
    "filesystem_write": FS_WRITE,
    "exec": EXEC,
    "process": EXEC,
    "subprocess": EXEC,
}


class ExecutionContext(str, Enum):
    """Who is driving the run.

    ``INTERACTIVE`` -- a user-triggered workflow.
    ``UNATTENDED``  -- a scheduler / batch job. Nobody can answer a prompt, so
                      only the pre-authorised unattended scope is honoured and
                      everything else is denied outright.
    """

    INTERACTIVE = "interactive"
    UNATTENDED = "unattended"


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


def normalize_permission(raw: Any) -> str:
    """Normalises one declared permission string to the canonical vocabulary."""
    if raw is None:
        return ""
    text = str(raw).strip().lower().replace(" ", "_")
    if not text:
        return ""
    if text in KNOWN_CAPABILITIES:
        return text
    alias = _ALIASES.get(text)
    if alias:
        return alias
    # Tolerate compound spellings such as "network:read:public".
    head = text.split(":", 1)[0]
    return _ALIASES.get(head, text)


def normalize_permissions(raw_permissions: Optional[Iterable[Any]]) -> List[str]:
    """Normalises a whole SKILL.md permissions list, preserving order."""
    if not raw_permissions:
        return []
    normalized: List[str] = []
    for item in raw_permissions:
        cap = normalize_permission(item)
        if cap and cap not in normalized:
            normalized.append(cap)
    return normalized


class NetworkPolicy(BaseModel):
    """Host-level egress policy for skills that declare a network capability.

    * ``allow_hosts`` empty **and** ``allow_any_host`` False -> no egress.
    * ``allow_any_host`` True -> egress is gated only by the skill's own
      declaration, with no host restriction. This is the default so that a
      missing configuration never silently breaks working skills, and it is
      always reported as a warning on the execution result.
    """

    allow_hosts: List[str] = Field(default_factory=list)
    allow_any_host: bool = False
    # Unattended runs are not trusted with egress unless explicitly enabled,
    # because a scheduled job consumes network budget with nobody watching.
    allow_unattended: bool = False

    def host_allowed(self, host: str) -> bool:
        if self.allow_any_host:
            return True
        candidate = (host or "").strip().lower().rstrip(".")
        if not candidate:
            return False
        for entry in self.allow_hosts:
            allowed = entry.strip().lower().lstrip("*.").rstrip(".")
            if not allowed:
                continue
            if candidate == allowed or candidate.endswith("." + allowed):
                return True
        return False

    def effective_allowlist(self) -> List[str]:
        return [WILDCARD_HOST] if self.allow_any_host else list(self.allow_hosts)

    def unrestricted(self) -> bool:
        return self.allow_any_host or not self.allow_hosts

    @classmethod
    def from_env(cls) -> "NetworkPolicy":
        raw_hosts = os.environ.get("COG_SKILL_NETWORK_ALLOW_HOSTS", "").strip()
        hosts = [h.strip() for h in raw_hosts.replace(";", ",").split(",") if h.strip()]
        raw_unattended = os.environ.get("COG_SKILL_NETWORK_ALLOW_UNATTENDED", "")
        allow_unattended = raw_unattended.strip().lower() in {"1", "true", "yes", "on"}
        if hosts:
            # NOTE: keep allow_unattended even when an explicit host allowlist
            # is configured. Dropping it here would silently deny every
            # scheduled run that *is* allowed to reach those hosts.
            return cls(
                allow_hosts=hosts,
                allow_any_host=False,
                allow_unattended=allow_unattended,
            )
        # No allowlist configured: fall back to unrestricted egress, which is
        # always reported as a warning on the execution result.
        return cls(
            allow_hosts=[],
            allow_any_host=True,
            allow_unattended=allow_unattended,
        )


class PolicyDecision(BaseModel):
    decision: Decision
    granted_capabilities: List[str] = Field(default_factory=list)
    denied_capabilities: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    context: ExecutionContext = ExecutionContext.INTERACTIVE
    normalized_permissions: List[str] = Field(default_factory=list)
    network_allowlist: List[str] = Field(default_factory=list)
    network_egress_allowed: bool = False

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


class SkillPermissionPolicy:
    """The one place that turns a permission declaration into a decision."""

    def __init__(
        self,
        network_policy: Optional[NetworkPolicy] = None,
        unattended_permissions: Optional[Iterable[str]] = None,
    ) -> None:
        self.network_policy = network_policy or NetworkPolicy()
        # Pre-authorised unattended scope. Empty by default: a scheduled job
        # gets no capability it did not explicitly negotiate.
        self.unattended_permissions = normalize_permissions(unattended_permissions)

    @classmethod
    def from_env(cls) -> "SkillPermissionPolicy":
        """Builds the policy purely from process environment.

        Two independent switches gate unattended (scheduled) runs, and both
        must be on:

        1. COG_SKILL_NETWORK_ALLOW_UNATTENDED -- network egress budget.
        2. ENV_UNATTENDED_ALLOW_PERMISSIONS -- the capability allowlist a
           scheduler may use with nobody watching.

        Neither is inferred from a skill's own permissions block, and
        neither defaults to permissive: an unset variable means the unattended
        scope is empty and every scheduled skill is denied, so the caller
        degrades instead of silently running with unapproved capability.
        """
        raw = os.environ.get(ENV_UNATTENDED_ALLOW_PERMISSIONS, "")
        caps = [c.strip() for c in raw.replace(";", ",").split(",") if c.strip()]
        return cls(
            network_policy=NetworkPolicy.from_env(),
            unattended_permissions=caps,
        )

    def evaluate(
        self,
        declared_permissions: Optional[Iterable[Any]],
        context: ExecutionContext = ExecutionContext.INTERACTIVE,
    ) -> PolicyDecision:
        declared = normalize_permissions(declared_permissions)
        denied: List[str] = []
        reasons: List[str] = []
        warnings: List[str] = []

        requested_network = [c for c in declared if c in NETWORK_CAPABILITIES]
        egress_allowed = False
        allowlist: List[str] = []

        if requested_network:
            policy = self.network_policy
            if not policy.effective_allowlist():
                denied.extend(requested_network)
                reasons.append(
                    "Network capability is declared but no host is authorised "
                    f"(COG_SKILL_NETWORK_ALLOW_HOSTS is empty and wildcard egress "
                    "is disabled). Denying instead of granting open internet access."
                )
            else:
                allowlist = policy.effective_allowlist()
                if context is ExecutionContext.UNATTENDED and not policy.allow_unattended:
                    denied.extend(requested_network)
                    reasons.append(
                        "Unattended execution cannot rely on an interactive "
                        "confirmation: network egress is denied unless it was "
                        "pre-authorised via COG_SKILL_NETWORK_ALLOW_UNATTENDED. "
                        "The caller must degrade."
                    )
                else:
                    egress_allowed = True
                    if policy.unrestricted():
                        warnings.append(
                            "Network egress for this skill is gated only by the "
                            "skill's own 'network:*' declaration -- no host "
                            "allowlist is configured, so it is not restricted to "
                            "specific domains."
                        )
        else:
            # No network declaration: egress stays off, and the runner will
            # install a deny-all guard in the child process.
            allowlist = []
            if declared:
                warnings.append(
                    "This skill declares no 'network:*' permission; all outbound "
                    "connections are blocked for this run."
                )

        if context is ExecutionContext.UNATTENDED:
            granted = [
                c for c in declared if c not in denied and c in self.unattended_permissions
            ]
            for cap in [c for c in declared if c not in denied and c not in granted]:
                denied.append(cap)
                reasons.append(
                    f"Capability '{cap}' is not in the pre-authorised unattended "
                    "scope; the caller must degrade rather than prompt."
                )
        else:
            granted = [c for c in declared if c not in denied]

        return PolicyDecision(
            decision=Decision.ALLOW if not denied else Decision.DENY,
            granted_capabilities=granted,
            denied_capabilities=denied,
            reasons=reasons,
            warnings=warnings,
            context=context,
            normalized_permissions=declared,
            network_allowlist=allowlist,
            network_egress_allowed=egress_allowed and not denied,
        )


def execution_context_from_env(default: ExecutionContext = ExecutionContext.INTERACTIVE) -> ExecutionContext:
    raw = os.environ.get("COG_SKILL_EXECUTION_CONTEXT", "").strip().lower()
    if raw in {c.value for c in ExecutionContext}:
        return ExecutionContext(raw)
    return default


__all__ = [
    "Decision",
    "ENV_UNATTENDED_ALLOW_PERMISSIONS",
    "EXEC",
    "EXTERNAL_CAPABILITIES",
    "ExecutionContext",
    "FS_ISOLATED",
    "FS_READ",
    "FS_WRITE",
    "KNOWN_CAPABILITIES",
    "NETWORK_CAPABILITIES",
    "NETWORK_READ",
    "NETWORK_WRITE",
    "NetworkPolicy",
    "PolicyDecision",
    "SkillPermissionPolicy",
    "WILDCARD_HOST",
    "execution_context_from_env",
    "normalize_permission",
    "normalize_permissions",
]
