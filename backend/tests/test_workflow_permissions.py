"""Regression tests for the centralized workflow permission / approval audit layer."""
from __future__ import annotations

import pytest

from app.core.skill_engine.policy import Decision as SkillDecision
from app.core.workflow_permissions import (
    ACTION_CREDENTIAL_EXPORT,
    ACTION_IMAGE_PROXY,
    ACTION_SCHEDULER_UNATTENDED,
    ACTION_SKILL_EXECUTE,
    ApprovalOutcome,
    AuditDecision,
    CallbackApprovalProvider,
    DenyAllApprovalProvider,
    InMemoryAuditSink,
    JsonlAuditSink,
    PermissionAction,
    RiskLevel,
    WorkflowDenied,
    WorkflowMode,
    WorkflowPermissionController,
    _reset_sink_for_tests,
    query_audit,
    require_authorization,
)


SCHEDULER_SCOPE = [
    "network:egress",
    "skill:exec",
    "network:read",
    "filesystem:isolated",
]


@pytest.fixture(autouse=True)
def _memory_sink():
    sink = InMemoryAuditSink()
    _reset_sink_for_tests(sink)
    yield sink
    _reset_sink_for_tests(None)


def _approve(_request):
    return ApprovalOutcome(approved=True, reason="human confirmed", approver_id="admin-1")


def _reject(_request):
    return ApprovalOutcome(approved=False, reason="operator declined")


# --------------------------------------------------------------------------- #
# interactive approval
# --------------------------------------------------------------------------- #


def test_interactive_approval_allows_and_audits():
    result = require_authorization(
        ACTION_IMAGE_PROXY,
        actor_id="u-1",
        mode=WorkflowMode.INTERACTIVE,
        approval_provider=CallbackApprovalProvider(_approve),
    )
    assert result.decision is AuditDecision.ALLOW
    records = query_audit(action="image.remote_proxy")
    assert len(records) == 1
    record = records[0]
    assert record.actor_id == "u-1"
    assert record.action == "image.remote_proxy"
    assert record.decision == AuditDecision.ALLOW
    assert record.when
    assert record.reason


def test_interactive_approval_denied_raises_and_blocks_action():
    ran = []
    with pytest.raises(WorkflowDenied):
        require_authorization(
            ACTION_CREDENTIAL_EXPORT,
            actor_id="u-1",
            mode=WorkflowMode.INTERACTIVE,
            approval_provider=CallbackApprovalProvider(_reject),
        )
        ran.append(1)
    assert ran == []
    decisions = [r.decision for r in query_audit(action="credential.export")]
    assert decisions == [AuditDecision.DENY]


def test_default_provider_is_deny_all():
    """No provider wired up must never mean 'allow'."""
    with pytest.raises(WorkflowDenied):
        require_authorization(
            ACTION_CREDENTIAL_EXPORT,
            actor_id="u-1",
            mode=WorkflowMode.INTERACTIVE,
            approval_provider=DenyAllApprovalProvider(),
        )


def test_approval_provider_exception_fails_closed():
    def boom(_request):
        raise RuntimeError("approval backend down")

    with pytest.raises(WorkflowDenied):
        require_authorization(
            ACTION_CREDENTIAL_EXPORT,
            actor_id="u-1",
            mode=WorkflowMode.INTERACTIVE,
            approval_provider=CallbackApprovalProvider(boom),
        )
    reasons = [r.reason for r in query_audit(action="credential.export")]
    assert any("approval_error" in reason for reason in reasons)


# --------------------------------------------------------------------------- #
# pre-authorization
# --------------------------------------------------------------------------- #


def test_pre_authorized_in_scope_allows():
    result = require_authorization(
        ACTION_IMAGE_PROXY,
        actor_id="u-1",
        mode=WorkflowMode.PRE_AUTHORIZED,
        pre_authorized=["network:egress"],
        approval_provider=CallbackApprovalProvider(_approve),
    )
    assert result.decision is AuditDecision.ALLOW
    assert result.granted_permissions == ["network:egress"]


def test_pre_authorized_out_of_scope_denied():
    with pytest.raises(WorkflowDenied):
        require_authorization(
            ACTION_IMAGE_PROXY,
            actor_id="u-1",
            mode=WorkflowMode.PRE_AUTHORIZED,
            pre_authorized=["credential:read"],
            approval_provider=CallbackApprovalProvider(_approve),
        )
    assert query_audit(action="image.remote_proxy")[0].reason.startswith(
        "outside_pre_authorized_scope"
    )


# --------------------------------------------------------------------------- #
# unattended
# --------------------------------------------------------------------------- #


class _AllowSkillPolicy:
    """Stands in for SkillPermissionPolicy; the real one is env-driven."""

    def __init__(self) -> None:
        self.calls: list = []

    def evaluate(self, capabilities, context=None):
        from app.core.skill_engine.policy import PolicyDecision

        self.calls.append((list(capabilities), context))
        return PolicyDecision(decision=SkillDecision.ALLOW, reason="stub-allow")


def test_unattended_inside_allowlist_allows():
    # skill:exec delegates to the real env-driven SkillPermissionPolicy, which
    # denies by default in tests; wire an explicit permissive policy.
    controller = WorkflowPermissionController(
        skill_policy=_AllowSkillPolicy(),
        pre_authorized=SCHEDULER_SCOPE,
        mode=WorkflowMode.UNATTENDED,
    )
    result = controller.authorize(ACTION_SCHEDULER_UNATTENDED, actor_id="7")
    assert result.decision is AuditDecision.ALLOW


def test_unattended_outside_allowlist_denied():
    controller = WorkflowPermissionController(
        skill_policy=_AllowSkillPolicy(),
        pre_authorized=["credential:read"],
        mode=WorkflowMode.UNATTENDED,
    )
    with pytest.raises(WorkflowDenied):
        controller.authorize(ACTION_SCHEDULER_UNATTENDED, actor_id="7")
    reason = query_audit(action="scheduler.unattended_run")[0].reason
    assert reason.startswith("outside_pre_authorized_scope")


# --------------------------------------------------------------------------- #
# fail closed on unknown / drift
# --------------------------------------------------------------------------- #


def test_unknown_mode_fails_closed():
    with pytest.raises(WorkflowDenied):
        require_authorization(
            ACTION_IMAGE_PROXY,
            actor_id="u-1",
            mode="semi-automatic",
            approval_provider=CallbackApprovalProvider(_approve),
        )
    assert query_audit(action="image.remote_proxy")[0].reason == "unknown_execution_mode"


def test_unregistered_action_fails_closed():
    rogue = PermissionAction(
        action="rogue.action",
        permissions=["network:egress"],
        risk=RiskLevel.HIGH,
        description="not in the registry",
    )
    with pytest.raises(WorkflowDenied):
        require_authorization(
            rogue, actor_id="u-1", mode=WorkflowMode.INTERACTIVE
        )
    assert query_audit()[0].reason == "undeclared_action"


def test_downgraded_declaration_fails_closed():
    """A caller cannot re-create a registered action with fewer permissions."""
    downgraded = PermissionAction(
        action=ACTION_SKILL_EXECUTE.action,
        permissions=[],
        risk=RiskLevel.LOW,
        description="tampered copy",
    )
    with pytest.raises(WorkflowDenied):
        require_authorization(downgraded, actor_id="u-1", mode=WorkflowMode.INTERACTIVE)
    assert query_audit()[0].reason == "undeclared_action"


def test_evaluator_failure_fails_closed(monkeypatch):
    controller = WorkflowPermissionController(
        pre_authorized=[], mode=WorkflowMode.INTERACTIVE
    )

    def boom(*_args, **_kwargs):
        raise ValueError("rubric blew up")

    monkeypatch.setattr(controller, "_decide", boom)
    with pytest.raises(WorkflowDenied):
        controller.authorize(ACTION_IMAGE_PROXY, actor_id="u-1")
    assert query_audit()[0].decision is AuditDecision.FAILURE


def test_audit_sink_failure_denies_action():
    class BrokenSink(InMemoryAuditSink):
        def append(self, record):
            raise OSError("disk full")

    _reset_sink_for_tests(BrokenSink())
    with pytest.raises(WorkflowDenied):
        require_authorization(
            ACTION_IMAGE_PROXY,
            actor_id="u-1",
            mode=WorkflowMode.INTERACTIVE,
            approval_provider=CallbackApprovalProvider(_approve),
        )


# --------------------------------------------------------------------------- #
# audit integrity
# --------------------------------------------------------------------------- #


def test_audit_records_are_complete_and_queryable():
    require_authorization(
        ACTION_IMAGE_PROXY,
        actor_id="alice",
        mode=WorkflowMode.INTERACTIVE,
        approval_provider=CallbackApprovalProvider(_approve),
    )
    with pytest.raises(WorkflowDenied):
        require_authorization(
            ACTION_CREDENTIAL_EXPORT,
            actor_id="bob",
            mode=WorkflowMode.INTERACTIVE,
        )
    by_actor = query_audit(actor_id="alice")
    assert len(by_actor) == 1
    assert by_actor[0].actor_id == "alice"
    denied = query_audit(decision=AuditDecision.DENY)
    assert denied and denied[0].action == "credential.export"
    assert denied[0].reason


def test_jsonl_sink_writes_hash_chain(tmp_path):
    sink = JsonlAuditSink(str(tmp_path / "audit.jsonl"))
    _reset_sink_for_tests(sink)
    for _ in range(3):
        require_authorization(
            ACTION_IMAGE_PROXY,
            actor_id="u-1",
            mode=WorkflowMode.INTERACTIVE,
            approval_provider=CallbackApprovalProvider(_approve),
        )
    assert len(sink.records()) == 3
    assert sink.verify_chain() is True
    assert (tmp_path / "audit.jsonl").exists()


def test_audit_cannot_be_skipped_by_business_code():
    """A denial is raised, so the guarded block is unreachable without audit."""
    reached = []

    def business_action():
        require_authorization(
            ACTION_CREDENTIAL_EXPORT,
            actor_id="u-1",
            mode=WorkflowMode.INTERACTIVE,
        )
        reached.append("ran")

    with pytest.raises(WorkflowDenied):
        business_action()
    assert reached == []
    assert query_audit(action="credential.export")


# --------------------------------------------------------------------------- #
# skill policy delegation
# --------------------------------------------------------------------------- #


def test_skill_capabilities_are_delegated_not_reimplemented():
    calls = {}

    from app.core.skill_engine.policy import PolicyDecision

    class RecordingPolicy:
        def evaluate(self, capabilities, context=None):
            calls["capabilities"] = list(capabilities)
            calls["context"] = context
            return PolicyDecision(decision=SkillDecision.ALLOW, reason="stub-allow")

    controller = WorkflowPermissionController(
        skill_policy=RecordingPolicy(),
        pre_authorized=SCHEDULER_SCOPE,
        mode=WorkflowMode.UNATTENDED,
    )
    controller.authorize(ACTION_SCHEDULER_UNATTENDED, actor_id="7")
    assert "network:egress" not in calls["capabilities"]
    assert "skill:exec" not in calls["capabilities"]
    assert calls["capabilities"] == ["network:read", "filesystem:isolated"]


# --------------------------------------------------------------------------- #
# WorkflowDenied carries a stable, machine-readable reason
# --------------------------------------------------------------------------- #

def test_workflow_denied_exposes_reason_matching_message():
    """Callers (scheduler logs, API handlers) read ``exc.reason``.

    If the attribute were missing the scheduler would raise an AttributeError
    while handling a denial, turning a clean fail-closed rejection into an
    unhandled crash. The reason must also be identical to the exception text
    so audit/UI layers do not have to re-derive it.
    """
    from app.core.workflow_permissions import (
        ACTION_CREDENTIAL_EXPORT,
        WorkflowDenied,
        require_authorization,
    )

    with pytest.raises(WorkflowDenied) as excinfo:
        require_authorization(ACTION_CREDENTIAL_EXPORT, actor_id="u-1")

    err = excinfo.value
    assert isinstance(err.reason, str)
    assert err.reason == str(err)
    assert err.reason.startswith("Action 'credential.export'")


def test_workflow_denied_reason_survives_all_deny_paths():
    """Every raise site must supply a reason string.

    Covers the four raise paths in the controller: unknown/unregistered
    action, denial decision, evaluator failure and audit-write failure.
    """
    from app.core.workflow_permissions import (
        PermissionAction,
        RiskLevel,
        WorkflowDenied,
        WorkflowMode,
        WorkflowPermissionController,
        AuditSink,
        AuditRecord,
    )

    # (a) unregistered / ad-hoc action
    controller = WorkflowPermissionController()
    ad_hoc = PermissionAction(
        action="not.registered",
        permissions=[],
        risk=RiskLevel.LOW,
        description="ad hoc",
    )
    with pytest.raises(WorkflowDenied) as excinfo:
        controller.authorize(ad_hoc, actor_id="u-1", mode=WorkflowMode.INTERACTIVE)
    assert excinfo.value.reason == str(excinfo.value)

    # (b) plain denial decision
    with pytest.raises(WorkflowDenied) as excinfo:
        require_authorization(
            "content.external_distribute",
            actor_id="u-1",
            mode=WorkflowMode.UNATTENDED,
        )
    assert excinfo.value.reason == str(excinfo.value)

    # (c) decision machinery blows up -> failure path
    controller = WorkflowPermissionController(
        approval_provider=CallbackApprovalProvider(_approve),
    )

    def boom(*_args, **_kwargs):
        raise RuntimeError('boom')

    mpatch = pytest.MonkeyPatch()
    mpatch.setattr(controller, '_decide', boom)
    try:
        with pytest.raises(WorkflowDenied) as excinfo:
            controller.authorize(
                ACTION_IMAGE_PROXY,
                actor_id='u-1',
                mode=WorkflowMode.INTERACTIVE,
            )
    finally:
        mpatch.undo()
    assert 'evaluation failed' in excinfo.value.reason
    assert excinfo.value.reason == str(excinfo.value)


def test_workflow_denied_reason_when_audit_write_fails():
    '''Audit failure must fail closed *and* still carry a reason.'''
    from app.core.workflow_permissions import InMemoryAuditSink as _Sink

    class BrokenSink(_Sink):
        def append(self, record):
            raise OSError('audit disk full')

    _reset_sink_for_tests(BrokenSink())
    with pytest.raises(WorkflowDenied) as excinfo:
        require_authorization(
            ACTION_IMAGE_PROXY,
            actor_id='u-1',
            mode=WorkflowMode.INTERACTIVE,
            approval_provider=CallbackApprovalProvider(_approve),
        )
    assert 'audit record could not be written' in excinfo.value.reason
    assert excinfo.value.reason == str(excinfo.value)
