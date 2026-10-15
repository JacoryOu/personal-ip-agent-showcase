"""Declared catalogue of the high-risk surfaces found in this repository."""

from __future__ import annotations

from app.core.workflow_permissions.declarations import PermissionAction
from app.core.workflow_permissions.registry import declare_action
from app.core.workflow_permissions.vocabulary import (
    PERM_CREDENTIAL_EXPORT,
    PERM_CREDENTIAL_READ,
    PERM_CREDENTIAL_WRITE,
    PERM_EXTERNAL_PUBLISH,
    PERM_NETWORK_EGRESS,
    PERM_PLATFORM_ACTION,
    PERM_SENSITIVE_FILE,
    PERM_SKILL_EXEC,
    PERM_WORKFLOW_WRITE,
    SKILL_CAP_FS_ISOLATED,
    SKILL_CAP_NETWORK_READ,
    RiskLevel,
)

ACTION_IMAGE_PROXY = declare_action(
    PermissionAction(
        action="image.remote_proxy",
        permissions=[PERM_NETWORK_EGRESS],
        risk=RiskLevel.MEDIUM,
        description="Server-side fetch of a user-supplied remote image URL.",
    )
)

ACTION_IMAGE_ENGINE_TEST = declare_action(
    PermissionAction(
        action="image.engine_connection_test",
        permissions=[PERM_NETWORK_EGRESS],
        risk=RiskLevel.MEDIUM,
        description="Outbound probe of the configured image engine with the server key.",
    )
)

ACTION_SKILL_EXECUTE = declare_action(
    PermissionAction(
        action="skill.execute",
        permissions=[PERM_SKILL_EXEC],
        risk=RiskLevel.HIGH,
        description="Any SkillManager skill execution started from application code.",
    )
)

ACTION_SCHEDULER_UNATTENDED = declare_action(
    PermissionAction(
        action="scheduler.unattended_run",
        # Concrete skill capabilities mirror skills/trending-radar/SKILL.md
        # (``network:read`` + ``filesystem:isolated``) so that the delegation to
        # SkillPermissionPolicy is meaningful instead of empty.
        permissions=[
            PERM_NETWORK_EGRESS,
            PERM_SKILL_EXEC,
            SKILL_CAP_NETWORK_READ,
            SKILL_CAP_FS_ISOLATED,
        ],
        risk=RiskLevel.HIGH,
        description="Unattended scheduled inspection work with no human present.",
    )
)

ACTION_CONTENT_DISTRIBUTE = declare_action(
    PermissionAction(
        action="content.external_distribute",
        permissions=[PERM_SKILL_EXEC, PERM_EXTERNAL_PUBLISH],
        risk=RiskLevel.HIGH,
        requires_explicit_approval=True,
        description="Publishing generated content to external platforms.",
    )
)

ACTION_PLATFORM_CRAWL = declare_action(
    PermissionAction(
        action="platform.crawl",
        permissions=[PERM_NETWORK_EGRESS, PERM_PLATFORM_ACTION],
        risk=RiskLevel.MEDIUM,
        description="Reading external platform content on behalf of a user.",
    )
)

ACTION_CREDENTIAL_SYNC = declare_action(
    PermissionAction(
        action="credential.provider_sync",
        permissions=[PERM_CREDENTIAL_READ, PERM_CREDENTIAL_WRITE, PERM_NETWORK_EGRESS],
        risk=RiskLevel.CRITICAL,
        requires_explicit_approval=True,
        description="Contacting a credential provider and mutating stored credentials.",
    )
)

ACTION_CREDENTIAL_EXPORT = declare_action(
    PermissionAction(
        action="credential.export",
        permissions=[PERM_CREDENTIAL_EXPORT],
        risk=RiskLevel.CRITICAL,
        requires_explicit_approval=True,
        description="Reading a raw secret out of the vault for export.",
    )
)

ACTION_VAULT_FILE_ACCESS = declare_action(
    PermissionAction(
        action="vault.sensitive_file",
        permissions=[PERM_SENSITIVE_FILE],
        risk=RiskLevel.HIGH,
        description="Touching a path inside the guarded vault region.",
    )
)

ACTION_PRODUCT_UPLOAD = declare_action(
    PermissionAction(
        action="upload.product_image",
        permissions=[PERM_WORKFLOW_WRITE],
        risk=RiskLevel.LOW,
        description="Owner-scoped product image upload written to the uploads directory.",
    )
)
