"""Declarative workflow actions and the approval-provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, List

from pydantic import BaseModel, Field

from app.core.workflow_permissions.vocabulary import (
    RiskLevel,
    WorkflowMode,
    normalize_workflow_permissions,
)

class PermissionAction(BaseModel):
    """A declarative description of one guarded workflow action."""

    action: str = Field(min_length=1)
    permissions: List[str] = Field(default_factory=list)
    risk: RiskLevel = RiskLevel.MEDIUM
    description: str = ""
    # When True this action must go through interactive approval regardless of
    # any pre-authorization, because the consequence is not reversible by
    # deleting a record.
    requires_explicit_approval: bool = False

    def declared_permissions(self) -> List[str]:
        return normalize_workflow_permissions(self.permissions)


class ApprovalRequest(BaseModel):
    actor_id: str
    action: str
    permissions: List[str]
    risk: RiskLevel
    mode: WorkflowMode
    reason: str = ""


class ApprovalOutcome(BaseModel):
    approved: bool
    reason: str = ""
    approver_id: str = ""


class ApprovalProvider(ABC):
    """Decides an interactive approval request."""

    @abstractmethod
    def request_approval(self, request: ApprovalRequest) -> ApprovalOutcome:
        ...


class CallbackApprovalProvider(ApprovalProvider):
    """Adapts a caller-supplied callable into an approval provider."""

    def __init__(self, callback: Callable[[ApprovalRequest], ApprovalOutcome]) -> None:
        self._callback = callback

    def request_approval(self, request: ApprovalRequest) -> ApprovalOutcome:
        return self._callback(request)


class DenyAllApprovalProvider(ApprovalProvider):
    """Default provider: nobody can approve anything. Fail closed."""

    def request_approval(self, request: ApprovalRequest) -> ApprovalOutcome:
        return ApprovalOutcome(
            approved=False,
            reason="no_approval_provider_configured",
            approver_id="",
        )
