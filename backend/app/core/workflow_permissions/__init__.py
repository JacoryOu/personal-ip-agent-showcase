"""Workflow permission approval + audit layer.

This package is split by concern:

* ``vocabulary``   -- permission tokens, modes, risk levels, ``WorkflowDenied``.
* ``declarations`` -- ``PermissionAction`` and the ``ApprovalProvider`` family.
* ``audit``        -- audit records/sinks incl. the JSONL hash-chained sink.
* ``controller``   -- the allow / deny / approval decision engine.
* ``registry``     -- process-wide catalogue of declared actions.
* ``catalogue``    -- the declared high-risk actions of this repository.

``app.core.workflow_permissions`` re-exports the full historical public API so
existing imports and tests keep working unchanged.
"""

from app.core.workflow_permissions.audit import (
    ENV_AUDIT_PATH,
    _reset_sink_for_tests,
    AuditRecord,
    AuditSink,
    InMemoryAuditSink,
    JsonlAuditSink,
)
from app.core.workflow_permissions.catalogue import (
    ACTION_CONTENT_DISTRIBUTE,
    ACTION_CREDENTIAL_EXPORT,
    ACTION_CREDENTIAL_SYNC,
    ACTION_IMAGE_ENGINE_TEST,
    ACTION_IMAGE_PROXY,
    ACTION_PLATFORM_CRAWL,
    ACTION_PRODUCT_UPLOAD,
    ACTION_SCHEDULER_UNATTENDED,
    ACTION_SKILL_EXECUTE,
    ACTION_VAULT_FILE_ACCESS,
)
from app.core.workflow_permissions.controller import (
    AuthorizationResult,
    WorkflowPermissionController,
    parse_pre_authorized,
    require_authorization,
)
from app.core.workflow_permissions.declarations import (
    ApprovalOutcome,
    ApprovalProvider,
    ApprovalRequest,
    CallbackApprovalProvider,
    DenyAllApprovalProvider,
    PermissionAction,
)
from app.core.workflow_permissions.registry import (
    declare_action,
    query_audit,
    registered_actions,
)
from app.core.workflow_permissions.vocabulary import (
    ENV_PRE_AUTHORIZED,
    KNOWN_WORKFLOW_PERMISSIONS,
    PERM_CREDENTIAL_EXPORT,
    PERM_CREDENTIAL_READ,
    PERM_CREDENTIAL_WRITE,
    PERM_EXTERNAL_PUBLISH,
    PERM_NETWORK_EGRESS,
    PERM_PLATFORM_ACTION,
    PERM_SENSITIVE_FILE,
    PERM_SKILL_EXEC,
    PERM_WORKFLOW_WRITE,
    SKILL_CAP_EXEC,
    SKILL_CAP_FS_ISOLATED,
    SKILL_CAP_FS_READ,
    SKILL_CAP_FS_WRITE,
    SKILL_CAP_NETWORK_READ,
    SKILL_CAP_NETWORK_WRITE,
    AuditDecision,
    RiskLevel,
    WorkflowDenied,
    WorkflowMode,
    normalize_workflow_permission,
    normalize_workflow_permissions,
)

__all__ = [
    "_reset_sink_for_tests",
    "ACTION_CONTENT_DISTRIBUTE",
    "ACTION_CREDENTIAL_EXPORT",
    "ACTION_CREDENTIAL_SYNC",
    "ACTION_IMAGE_ENGINE_TEST",
    "ACTION_IMAGE_PROXY",
    "ACTION_PLATFORM_CRAWL",
    "ACTION_PRODUCT_UPLOAD",
    "ACTION_SCHEDULER_UNATTENDED",
    "ACTION_SKILL_EXECUTE",
    "ACTION_VAULT_FILE_ACCESS",
    "ApprovalOutcome",
    "ApprovalProvider",
    "ApprovalRequest",
    "AuditDecision",
    "AuditRecord",
    "AuditSink",
    "AuthorizationResult",
    "CallbackApprovalProvider",
    "declare_action",
    "DenyAllApprovalProvider",
    "ENV_AUDIT_PATH",
    "ENV_PRE_AUTHORIZED",
    "InMemoryAuditSink",
    "JsonlAuditSink",
    "KNOWN_WORKFLOW_PERMISSIONS",
    "normalize_workflow_permission",
    "normalize_workflow_permissions",
    "parse_pre_authorized",
    "PERM_CREDENTIAL_EXPORT",
    "PERM_CREDENTIAL_READ",
    "PERM_CREDENTIAL_WRITE",
    "PERM_EXTERNAL_PUBLISH",
    "PERM_NETWORK_EGRESS",
    "PERM_PLATFORM_ACTION",
    "PERM_SENSITIVE_FILE",
    "PERM_SKILL_EXEC",
    "PERM_WORKFLOW_WRITE",
    "PermissionAction",
    "query_audit",
    "registered_actions",
    "require_authorization",
    "RiskLevel",
    "SKILL_CAP_EXEC",
    "SKILL_CAP_FS_ISOLATED",
    "SKILL_CAP_FS_READ",
    "SKILL_CAP_FS_WRITE",
    "SKILL_CAP_NETWORK_READ",
    "SKILL_CAP_NETWORK_WRITE",
    "WorkflowDenied",
    "WorkflowMode",
    "WorkflowPermissionController",
]
