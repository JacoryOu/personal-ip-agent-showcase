"""The workflow permission decision engine (allow / deny / approval)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, List, Optional

from app.core.skill_engine.policy import (
    KNOWN_CAPABILITIES,
    Decision as SkillDecision,
    ExecutionContext,
    SkillPermissionPolicy,
)
from app.core.workflow_permissions.audit import _append_audit, _build_record
from app.core.workflow_permissions.declarations import (
    ApprovalProvider,
    ApprovalRequest,
    DenyAllApprovalProvider,
    PermissionAction,
)
import app.core.workflow_permissions.registry as _registry_module
from app.core.workflow_permissions.vocabulary import (
    ENV_PRE_AUTHORIZED,
    PERM_SKILL_EXEC,
    AuditDecision,
    RiskLevel,
    WorkflowDenied,
    WorkflowMode,
    _RISK_ORDER,
    _validate_permission_token,
    normalize_workflow_permissions,
)
from app.core.workflow_permissions.results import (
    AuthorizationResult,
    parse_pre_authorized,
)

logger = logging.getLogger(__name__)

class WorkflowPermissionController:
    """The only supported entry point for authorising a guarded action."""

    def __init__(
        self,
        *,
        skill_policy: Optional[SkillPermissionPolicy] = None,
        approval_provider: Optional[ApprovalProvider] = None,
        pre_authorized: Optional[Iterable[str]] = None,
        mode: WorkflowMode = WorkflowMode.INTERACTIVE,
    ) -> None:
        self._skill_policy = skill_policy
        self._approval_provider = approval_provider or DenyAllApprovalProvider()
        self._pre_authorized = (
            normalize_workflow_permissions(pre_authorized)
            if pre_authorized is not None
            else parse_pre_authorized()
        )
        self._mode = mode

    # -- helpers ---------------------------------------------------------- #

    @staticmethod
    def _skill_policy_or_default(
        policy: Optional[SkillPermissionPolicy],
    ) -> SkillPermissionPolicy:
        return policy if policy is not None else SkillPermissionPolicy.from_env()

    def _audit(
        self,
        *,
        actor_id: str,
        declaration: Optional[PermissionAction],
        mode: WorkflowMode,
        decision: AuditDecision,
        reason: str,
        permissions: Optional[List[str]] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> str:
        record = _build_record(
            actor_id=actor_id,
            action=declaration.action if declaration else "<undeclared>",
            permissions=permissions
            if permissions is not None
            else (declaration.declared_permissions() if declaration else []),
            risk=declaration.risk if declaration else RiskLevel.CRITICAL,
            mode=mode,
            decision=decision,
            reason=reason,
            detail=detail,
        )
        _append_audit(record)
        return record.id

    # -- public API ------------------------------------------------------- #

    def authorize(
        self,
        declaration: PermissionAction,
        *,
        actor_id: str,
        mode: Optional[Any] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> AuthorizationResult:
        """Decide and audit one action.

        HONESTY / fail-closed contract: this returns **only** on ALLOW. A denial
        raises :class:`WorkflowDenied` after the denial has been audited, so a
        caller cannot accidentally ignore a DENY and run the action anyway.
        """
        effective_mode: Any = mode if mode is not None else self._mode

        # 0) A caller that passes a raw string (or anything that is not a
        #    PermissionAction) is not a declaration. Deny cleanly instead of
        #    raising AttributeError while trying to audit it.
        if not isinstance(declaration, PermissionAction):
            raw = declaration if isinstance(declaration, str) else repr(declaration)
            try:
                self._audit(
                    actor_id=actor_id,
                    declaration=None,
                    mode=effective_mode
                    if isinstance(effective_mode, WorkflowMode)
                    else WorkflowMode.INTERACTIVE,
                    decision=AuditDecision.DENY,
                    reason='undeclared_action',
                    permissions=[],
                )
            except Exception:
                logger.exception('Workflow audit write failed while recording failure')
            raise WorkflowDenied(
                f"Action '{raw}' denied: undeclared_action"
            )

        try:
            result = self._decide(
                declaration,
                actor_id=actor_id,
                mode=effective_mode,
                detail=detail or {},
            )
        except WorkflowDenied:
            raise
        except Exception as exc:  # fail closed on any evaluator defect
            logger.exception("Workflow permission evaluator failure")
            try:
                self._audit(
                    actor_id=actor_id,
                    declaration=declaration,
                    mode=effective_mode,
                    decision=AuditDecision.FAILURE,
                    reason=f"evaluator_failure:{exc.__class__.__name__}",
                )
            except Exception:
                logger.exception("Workflow audit write failed while recording failure")
            raise WorkflowDenied(
                f"Action '{declaration.action}' denied: permission evaluation failed"
            ) from exc
        if result.decision is not AuditDecision.ALLOW:
            raise WorkflowDenied(
                f"Action '{declaration.action}' denied: {result.reason}"
            )
        return result

    def _decide(
        self,
        declaration: PermissionAction,
        *,
        actor_id: str,
        mode: WorkflowMode,
        detail: Dict[str, Any],
    ) -> AuthorizationResult:
        # 0) Trust boundary: only declarations that came from the registry are
        #    honoured. An ad-hoc PermissionAction (or a downgraded copy of a
        #    registered one) is denied rather than evaluated.
        if not _registry_module.REGISTRY.matches(declaration):
            return self._deny(
                declaration,
                actor_id,
                mode if isinstance(mode, WorkflowMode) else WorkflowMode.INTERACTIVE,
                "undeclared_action",
                declaration.declared_permissions(),
            )

        permissions = declaration.declared_permissions()

        # 1) Unknown / malformed declaration -> fail closed.
        #    The mode is normalised defensively: a caller passing a raw string
        #    that is not a WorkflowMode must be denied, never coerced into an
        #    "interactive" run.
        resolved_mode: Optional[WorkflowMode] = None
        if isinstance(mode, WorkflowMode):
            resolved_mode = mode
        else:
            try:
                resolved_mode = WorkflowMode(str(mode))
            except (ValueError, TypeError):
                resolved_mode = None
        if resolved_mode is None:
            return self._deny(
                declaration, actor_id, mode, "unknown_execution_mode", permissions
            )
        mode = resolved_mode
        if not declaration.action.strip():
            return self._deny(
                declaration, actor_id, mode, "unknown_action", permissions
            )
        unknown_perms = [p for p in permissions if not _validate_permission_token(p)]
        if unknown_perms:
            return self._deny(
                declaration,
                actor_id,
                mode,
                f"unknown_permission:{','.join(sorted(unknown_perms))}",
                permissions,
            )

        # 2) Skill capability delegation -- never re-implemented here.
        if PERM_SKILL_EXEC in permissions:
            # Only genuine skill capabilities are delegated. Workflow-level
            # permissions (credential:*, workflow:*, external:publish, ...)
            # are NOT skill capabilities and must not be passed to the skill
            # policy, which would otherwise see them as unknown tokens.
            skill_caps = [p for p in permissions if p in KNOWN_CAPABILITIES]
            skill_decision = self._skill_policy_or_default(self._skill_policy).evaluate(
                skill_caps,
                context=(
                    ExecutionContext.UNATTENDED
                    if mode is WorkflowMode.UNATTENDED
                    else ExecutionContext.INTERACTIVE
                ),
            )
            if skill_decision.decision is not SkillDecision.ALLOW:
                return self._deny(
                    declaration,
                    actor_id,
                    mode,
                    f"skill_policy_denied:{skill_decision.decision.value}",
                    permissions,
                )

        # 3) Mode-specific behaviour.
        if mode is WorkflowMode.UNATTENDED:
            missing = [p for p in permissions if p not in self._pre_authorized]
            if missing:
                return self._deny(
                    declaration,
                    actor_id,
                    mode,
                    f"outside_pre_authorized_scope:{','.join(sorted(missing))}",
                    permissions,
                )
            return self._allow(declaration, actor_id, mode, permissions, detail)

        if mode is WorkflowMode.PRE_AUTHORIZED:
            if permissions and not set(permissions).issubset(set(self._pre_authorized)):
                return self._deny(
                    declaration,
                    actor_id,
                    mode,
                    "outside_pre_authorized_scope",
                    permissions,
                )
            if declaration.requires_explicit_approval:
                return self._interactive(
                    declaration, actor_id, mode, permissions, detail,
                    reason="explicit_approval_required",
                )
            return self._allow(declaration, actor_id, mode, permissions, detail)

        # INTERACTIVE
        needs_approval = (
            declaration.requires_explicit_approval
            or _RISK_ORDER[declaration.risk] >= _RISK_ORDER[RiskLevel.HIGH]
        )
        if needs_approval:
            return self._interactive(
                declaration, actor_id, mode, permissions, detail,
                reason="high_risk_requires_approval",
            )
        return self._allow(declaration, actor_id, mode, permissions, detail)

    # -- decision helpers -------------------------------------------------- #

    def _interactive(
        self,
        declaration: PermissionAction,
        actor_id: str,
        mode: WorkflowMode,
        permissions: List[str],
        detail: Dict[str, Any],
        *,
        reason: str,
    ) -> AuthorizationResult:
        request = ApprovalRequest(
            actor_id=actor_id,
            action=declaration.action,
            permissions=permissions,
            risk=declaration.risk,
            mode=mode,
            reason=reason,
        )
        try:
            outcome = self._approval_provider.request_approval(request)
        except Exception as exc:
            logger.exception("Approval provider raised; denying")
            return self._deny(
                declaration, actor_id, mode, f"approval_error:{exc.__class__.__name__}",
                permissions,
            )
        if outcome is None or not outcome.approved:
            why = outcome.reason if outcome is not None else "approval_no_outcome"
            return self._deny(declaration, actor_id, mode, f"approval_denied:{why}", permissions)
        return self._allow(declaration, actor_id, mode, permissions, detail)

    def _allow(
        self,
        declaration: PermissionAction,
        actor_id: str,
        mode: WorkflowMode,
        permissions: List[str],
        detail: Dict[str, Any],
    ) -> AuthorizationResult:
        try:
            audit_id = self._audit(
                actor_id=actor_id,
                declaration=declaration,
                mode=mode,
                decision=AuditDecision.ALLOW,
                reason="authorized",
                permissions=permissions,
                detail=detail,
            )
        except Exception as exc:
            logger.exception("Audit write failed; failing closed")
            raise WorkflowDenied(
                f"Action '{declaration.action}' denied: audit record could not be written"
            ) from exc
        return AuthorizationResult(
            decision=AuditDecision.ALLOW,
            action=declaration.action,
            reason="authorized",
            granted_permissions=permissions,
            audit_id=audit_id,
        )

    def _deny(
        self,
        declaration: PermissionAction,
        actor_id: str,
        mode: WorkflowMode,
        reason: str,
        permissions: List[str],
    ) -> AuthorizationResult:
        try:
            audit_id = self._audit(
                actor_id=actor_id,
                declaration=declaration,
                mode=mode,
                decision=AuditDecision.DENY,
                reason=reason,
                permissions=permissions,
            )
        except Exception as exc:
            logger.exception("Audit write failed while recording a denial")
            raise WorkflowDenied(
                f"Action '{declaration.action}' denied: audit record could not be written"
            ) from exc
        return AuthorizationResult(
            decision=AuditDecision.DENY,
            action=declaration.action,
            reason=reason,
            audit_id=audit_id,
        )


def require_authorization(
    declaration: PermissionAction,
    *,
    actor_id: str,
    mode: Optional[Any] = None,
    approval_provider: Optional[ApprovalProvider] = None,
    pre_authorized: Optional[Iterable[str]] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> AuthorizationResult:
    """One-shot helper for a single guarded action."""
    controller = WorkflowPermissionController(
        approval_provider=approval_provider,
        pre_authorized=pre_authorized,
        mode=mode or WorkflowMode.INTERACTIVE,
    )
    return controller.authorize(
        declaration, actor_id=actor_id, mode=mode, detail=detail
    )
