# -*- coding: utf-8 -*-
"""Tests for the NTFS ACL enforcement layer.

STATUS: this layer is **Partial**, but no longer plan-only.

- ``dry_run=True`` (the default) only computes the plan and never writes.
- ``dry_run=False`` on Windows really calls ``SetNamedSecurityInfoW`` to add a
  scoped allow ACE for the resolved principal.
- The write is read back and verified; a failed verification fails closed and
  does not return a usable plan.
- A normal runner exit performs a best-effort rollback to the original DACL.
- A crashed runner can still leave the ACE behind, and rollback failures are
  reported for manual repair.

This is still not full container isolation: there is no dedicated sandbox
account, no AppContainer, no OS network boundary and no job object.
"""
from pathlib import Path
import sys

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest

from app.core.skill_engine.acl_guard import (
    AclPlanError,
    build_acl_plan,
    resolve_acl_target,
)

SID = "S-1-5-21-1-2-3-1001"
FS_READ = "filesystem:read"
FS_WRITE = "filesystem:write"
FS_ISOLATED = "filesystem:isolated"


@pytest.fixture()
def workspace(tmp_path):
    target = tmp_path / "cog_sandbox_ws"
    target.mkdir()
    return target


# --- capability -> rights mapping ------------------------------------------

def test_read_capability_plans_read_only(workspace):
    plan = build_acl_plan(workspace, SID, [FS_READ])
    allow = [e for e in plan.entries if e.allow]
    assert allow[0].rights == ["read"]


def test_write_capability_plans_write(workspace):
    plan = build_acl_plan(workspace, SID, [FS_WRITE])
    allow = [e for e in plan.entries if e.allow]
    assert allow[0].rights == ["write"]


def test_read_plus_write_plans_both(workspace):
    plan = build_acl_plan(workspace, SID, [FS_READ, FS_WRITE])
    allow = [e for e in plan.entries if e.allow]
    assert allow[0].rights == ["read", "write"]


def test_isolated_implies_read_and_write(workspace):
    plan = build_acl_plan(workspace, SID, [FS_ISOLATED])
    allow = [e for e in plan.entries if e.allow]
    assert allow[0].rights == ["read", "write"]


def test_parent_deny_is_planned(workspace):
    plan = build_acl_plan(workspace, SID, [FS_WRITE])
    deny = [e for e in plan.entries if not e.allow]
    assert deny and deny[0].rights == ["write", "delete"]


def test_every_entry_names_the_supplied_principal(workspace):
    plan = build_acl_plan(workspace, SID, [FS_READ, FS_WRITE])
    assert all(entry.principal == SID for entry in plan.entries)


# --- fail-closed paths ------------------------------------------------------

def test_missing_principal_fails_closed(workspace):
    with pytest.raises(AclPlanError) as exc:
        build_acl_plan(workspace, None, [FS_READ])
    assert "SID" in str(exc.value)


def test_no_filesystem_capability_fails_closed(workspace):
    with pytest.raises(AclPlanError) as exc:
        build_acl_plan(workspace, SID, ["network:read"])
    assert "nothing to plan" in str(exc.value)


def test_empty_capability_list_fails_closed(workspace):
    with pytest.raises(AclPlanError):
        build_acl_plan(workspace, SID, [])


def test_missing_directory_fails_closed(tmp_path):
    with pytest.raises(AclPlanError) as exc:
        build_acl_plan(tmp_path / "does_not_exist", SID, [FS_READ])
    assert "not an existing directory" in str(exc.value)


def test_file_target_fails_closed(tmp_path):
    target = tmp_path / "a_file.txt"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(AclPlanError):
        build_acl_plan(target, SID, [FS_READ])


def test_relative_escape_is_refused(workspace, monkeypatch):
    with pytest.raises(AclPlanError):
        resolve_acl_target(workspace.parent / ".." / workspace.parent.name)


def test_system_directory_is_refused():
    system_dir = Path("C:/Windows/System32/config")
    if not system_dir.exists():
        pytest.skip("Windows system layout not present on this host")
    with pytest.raises(AclPlanError):
        build_acl_plan(system_dir, SID, [FS_READ])


def test_caller_declared_protected_root_is_refused(workspace):
    """A caller-declared protected root must be refused as a target too."""
    protected = [workspace / "guarded"]
    protected[0].mkdir()
    with pytest.raises(AclPlanError):
        build_acl_plan(protected[0], SID, [FS_READ], protected_roots=protected)


def test_ordinary_target_is_not_refused_by_unrelated_protected_root(workspace):
    """Declaring an unrelated protected root must not refuse a normal target."""
    other = workspace.parent / "somewhere_else"
    other.mkdir(exist_ok=True)
    plan = build_acl_plan(workspace, SID, [FS_READ], protected_roots=[other])
    assert plan.enforced is False


def test_filesystem_root_is_refused(workspace):
    resolved = workspace.resolve()
    root = Path(resolved.anchor)
    if not root.exists():
        pytest.skip("No filesystem root available on this host")
    with pytest.raises(AclPlanError):
        resolve_acl_target(root)


# --- honesty: plan-only vs real enforcement -------------------------------

def test_dry_run_is_the_default_and_never_enforces(workspace):
    for caps in ([FS_READ], [FS_WRITE], [FS_ISOLATED], [FS_READ, FS_WRITE]):
        plan = build_acl_plan(workspace, SID, caps)
        assert plan.dry_run is True
        assert plan.enforced is False


def test_dry_run_plan_carries_the_plan_only_warning(workspace):
    plan = build_acl_plan(workspace, SID, [FS_READ])
    assert any("ACL PLAN ONLY" in w for w in plan.warnings)
    assert any("SetNamedSecurityInfoW" in w for w in plan.warnings)


def test_describe_reports_enforced_false_for_dry_run(workspace):
    described = build_acl_plan(workspace, SID, [FS_READ]).describe()
    assert described["enforced"] is False
    assert described["dry_run"] is True


def test_enforce_applies_verifies_and_rolls_back(workspace):
    """dry_run=False really writes the scoped DACL, verifies it, then restores."""
    if sys.platform != "win32":
        pytest.skip("NTFS enforcement is Windows-only")

    plan = build_acl_plan(workspace, SID, [FS_WRITE], dry_run=False)
    try:
        assert plan.dry_run is False
        assert plan.enforced is True
        assert plan.rollback is not None
        assert plan.entries[0].applied is True
        assert any("SetNamedSecurityInfoW" in w for w in plan.warnings)
    finally:
        notes = plan.restore()
    assert any("Restored" in n for n in notes)
    assert plan.restore() == [
        "ACL rollback was already performed; nothing to restore."
    ]


@pytest.mark.parametrize("principal", ["not-a-sid", "S-1", "S-999"])
def test_enforce_with_a_malformed_principal_fails_closed(workspace, principal):
    """A syntactically invalid principal must abort before any DACL write.

    A well-formed but non-existent SID (for example ``S-1-5-21-1-2-3-1001``) is
    *not* an error: it is still a valid security identifier and can legitimately
    be written into an ACE. Only unparsable input fails closed here.
    """
    if sys.platform != "win32":
        pytest.skip("NTFS enforcement is Windows-only")
    with pytest.raises(AclPlanError):
        build_acl_plan(workspace, principal, [FS_WRITE], dry_run=False)
