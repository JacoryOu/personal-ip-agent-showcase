"""Regression tests for the OS-level network boundary *planning* layer.

These tests exist to pin the honesty contract: the module computes and
describes an intended Windows Firewall policy, and never claims to enforce
one. ``NetworkBoundaryPlan.enforced`` is always False in this build.
"""

from __future__ import annotations

import pytest

from app.core.skill_engine.os_network_boundary import (
    NetworkBoundaryPlan,
    build_network_boundary_plan,
)
from app.core.skill_engine.policy import NETWORK_READ, NETWORK_WRITE, WILDCARD_HOST


def test_disabled_mode_warns_that_only_the_python_guard_remains():
    plan = build_network_boundary_plan("disabled", ["example.com"], [NETWORK_READ], True)

    assert plan.mode == "disabled"
    assert plan.rules == []
    assert plan.enforced is False
    assert plan.ok is True
    assert any("DISABLED" in w for w in plan.warnings)


def test_disabled_mode_does_not_block_execution():
    plan = build_network_boundary_plan("disabled", [], [], False)
    assert plan.blocking_errors == []


def test_unknown_mode_fails_closed():
    plan = build_network_boundary_plan("nonsense", ["example.com"], [NETWORK_READ], True)

    assert plan.ok is False
    assert plan.blocking_errors
    assert plan.enforced is False


def test_enforce_request_is_rejected_rather_than_degraded():
    plan = build_network_boundary_plan(
        "enforce", ["example.com"], [NETWORK_READ], True
    )

    assert plan.ok is False
    assert plan.blocking_errors
    assert plan.enforced is False
    # It still describes what it *would* have done, so an operator can act.
    assert any("firewall" in e.lower() for e in plan.blocking_errors)


def test_dry_run_without_egress_is_a_deny_all_plan():
    plan = build_network_boundary_plan("dry_run", [], [], False)

    assert plan.ok is True
    assert plan.enforced is False
    assert len(plan.rules) == 1
    rule = plan.rules[0]
    assert rule.action == "BLOCK"
    assert rule.remote_addresses == ["*"]
    assert rule.remote_ports == ["*"]


def test_dry_run_read_only_limits_ports_to_web():
    plan = build_network_boundary_plan(
        "dry_run", ["example.com", "docs.example.com"], [NETWORK_READ], True
    )

    allow = [r for r in plan.rules if r.action == "ALLOW"]
    assert len(allow) == 1
    assert allow[0].remote_addresses == ["docs.example.com", "example.com"]
    assert allow[0].remote_ports == ["80", "443"]


def test_dry_run_network_write_widens_ports_and_warns_it_is_a_plan_only():
    plan = build_network_boundary_plan(
        "dry_run", ["example.com"], [NETWORK_READ, NETWORK_WRITE], True
    )

    allow = [r for r in plan.rules if r.action == "ALLOW"][0]
    assert "*" in allow.remote_ports
    assert any("PLAN ONLY" in w for w in plan.warnings)


def test_wildcard_host_is_called_out_as_a_hole():
    plan = build_network_boundary_plan(
        "dry_run", [WILDCARD_HOST], [NETWORK_READ], True
    )

    allow = [r for r in plan.rules if r.action == "ALLOW"][0]
    assert allow.remote_addresses == ["*"]
    assert any("'*'" in w for w in plan.warnings)


def test_egress_allowed_with_empty_allowlist_produces_no_allow_rule():
    plan = build_network_boundary_plan("dry_run", [], [NETWORK_READ], True)

    assert plan.rules == []
    assert any("allowlist is empty" in w for w in plan.warnings)
    assert plan.enforced is False


def test_describe_does_not_overstate_enforcement():
    plan = build_network_boundary_plan("dry_run", ["example.com"], [NETWORK_READ], True)
    described = plan.describe()

    assert described["enforced"] is False
    assert isinstance(described["rules"], list)


def test_plan_type_defaults_to_not_enforced():
    assert NetworkBoundaryPlan(mode="dry_run").enforced is False


@pytest.mark.parametrize("mode", ["disabled", "dry_run", "enforce"])
def test_enforced_is_false_in_every_mode(mode):
    plan = build_network_boundary_plan(mode, ["example.com"], [NETWORK_READ], True)
    assert plan.enforced is False
