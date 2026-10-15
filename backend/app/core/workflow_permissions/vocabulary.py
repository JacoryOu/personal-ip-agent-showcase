"""Workflow permission vocabulary: tokens, modes, risk levels, denial type.

Kept separate from declarations / audit / controller so every layer can import
the vocabulary without pulling in the rest of the permission package.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, List, Optional

from app.core.skill_engine.policy import KNOWN_CAPABILITIES

PERM_NETWORK_EGRESS = "network:egress"
PERM_SKILL_EXEC = "skill:exec"
PERM_EXTERNAL_PUBLISH = "external:publish"
PERM_PLATFORM_ACTION = "platform:action"
PERM_CREDENTIAL_READ = "credential:read"
PERM_CREDENTIAL_WRITE = "credential:write"
PERM_CREDENTIAL_EXPORT = "credential:export"
PERM_SENSITIVE_FILE = "sensitive_file:access"
PERM_WORKFLOW_WRITE = "workflow:write"

# Canonical skill capability tokens re-used verbatim as second-class workflow
# permissions. An action that executes a skill must name the concrete
# capabilities that skill will use, otherwise the delegation to
# SkillPermissionPolicy would receive an empty capability list and any
# capability check would be vacuous.
SKILL_CAP_NETWORK_READ = "network:read"
SKILL_CAP_NETWORK_WRITE = "network:write"
SKILL_CAP_FS_READ = "filesystem:read"
SKILL_CAP_FS_WRITE = "filesystem:write"
SKILL_CAP_FS_ISOLATED = "filesystem:isolated"
SKILL_CAP_EXEC = "exec"

KNOWN_WORKFLOW_PERMISSIONS = frozenset(
    {
        PERM_NETWORK_EGRESS,
        PERM_SKILL_EXEC,
        PERM_EXTERNAL_PUBLISH,
        PERM_PLATFORM_ACTION,
        PERM_CREDENTIAL_READ,
        PERM_CREDENTIAL_WRITE,
        PERM_CREDENTIAL_EXPORT,
        PERM_SENSITIVE_FILE,
        PERM_WORKFLOW_WRITE,
    }
)

# Permission tokens are namespaced either by a skill capability ("network:read")
# or by the workflow vocabulary above. Anything else is unknown.
_SKILL_CAPABILITY_PREFIXES = ("network:", "filesystem:", "exec")

ENV_PRE_AUTHORIZED = "COG_WORKFLOW_PRE_AUTHORIZED"
ENV_AUDIT_PATH = "COG_WORKFLOW_AUDIT_PATH"


class WorkflowMode(str, Enum):
    """Who is driving the workflow step."""

    INTERACTIVE = "interactive"
    PRE_AUTHORIZED = "pre_authorized"
    UNATTENDED = "unattended"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_RISK_ORDER = {r: i for i, r in enumerate(
    (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
)}


class AuditDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    FAILURE = "failure"


class WorkflowDenied(Exception):
    """Raised when a workflow action is not authorised. Fail closed.

    ``reason`` is the single machine-readable string that callers (and the
    audit layer) rely on. It is always identical to the exception text, so a
    caller can log or surface it without re-deriving the cause.
    """

    def __init__(self, reason: str) -> None:
        self.reason = str(reason)
        super().__init__(self.reason)


# --------------------------------------------------------------------------- #
# Declarations
# --------------------------------------------------------------------------- #


def normalize_workflow_permission(raw: Any) -> str:
    """Normalise one *workflow* permission token.

    HONESTY NOTE: this deliberately does **not** reuse
    ``skill_engine.policy.normalize_permissions``. That function maps aliases
    such as ``network`` -> ``network:read`` and ``process`` -> ``exec``, which
    is right for a ``SKILL.md`` capability block but wrong here: it would
    silently rewrite workflow tokens (``skill:exec``, ``network:egress``,
    ``credential:export``) into skill capabilities. Only case/whitespace is
    normalised so an unrecognised token stays unrecognised and fails closed.
    """
    if raw is None:
        return ""
    return str(raw).strip().lower()


def normalize_workflow_permissions(raw_permissions: Optional[Iterable[Any]]) -> List[str]:
    """Trim / lowercase a workflow permission list, preserving order."""
    if not raw_permissions:
        return []
    out: List[str] = []
    for item in raw_permissions:
        token = normalize_workflow_permission(item)
        if token:
            out.append(token)
    return out


def _validate_permission_token(token: str) -> bool:
    """Only the closed vocabulary is accepted. Unknown tokens fail closed."""
    if token in KNOWN_WORKFLOW_PERMISSIONS:
        return True
    # Concrete skill capabilities are legal second-class tokens: an action that
    # runs a skill must be able to name what that skill actually needs so the
    # skill policy can be delegated to.
    return token in KNOWN_CAPABILITIES
