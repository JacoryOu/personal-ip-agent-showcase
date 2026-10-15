"""Authorization result type + pre-authorization allowlist parsing.

Kept separate from :mod:`controller` so the decision engine file stays within the
repository review threshold.
"""

from __future__ import annotations

import os
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.workflow_permissions.vocabulary import (
    ENV_PRE_AUTHORIZED,
    AuditDecision,
    normalize_workflow_permissions,
)


class AuthorizationResult(BaseModel):
    """Successful authorization outcome. A denial raises ``WorkflowDenied``."""

    decision: AuditDecision
    action: str
    reason: str
    granted_permissions: List[str] = Field(default_factory=list)
    audit_id: str = ""


def parse_pre_authorized(raw: Optional[str] = None) -> List[str]:
    """Parse the pre-authorization allowlist. Unset => empty => deny by default."""
    if raw is None:
        raw = os.environ.get(ENV_PRE_AUTHORIZED, "")
    caps = [c.strip() for c in str(raw).replace(";", ",").split(",") if c.strip()]
    return normalize_workflow_permissions(caps)
