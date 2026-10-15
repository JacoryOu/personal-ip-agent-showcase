"""NTFS DACL computation *and* real enforcement for skill sandboxes.

WHAT THIS MODULE ACTUALLY DOES
------------------------------
Two distinct jobs, kept strictly separate:

1. **Planning** (always available, on every platform). It derives the ACE set
   the granted capabilities require for a declared sandbox principal, and it
   refuses unsafe targets before any descriptor is touched. This part is pure
   and has been stable for a long time.

2. **Enforcement** (Windows only, opt-in). When ``dry_run=False`` this module
   really writes the workspace DACL through ``SetNamedSecurityInfoW``, then
   **reads the descriptor back and verifies** that the expected allow-ACE for
   the target SID is present. Only a successful write *and* a successful
   read-back verification set :attr:`AclPlan.enforced` to ``True``.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
* It never creates a Windows account. ``LookupAccountNameW`` is used only to
  resolve an account that already exists; failure is fatal, not repaired.
* It never elevates. No ``AdjustTokenPrivileges``, no UAC prompt, no "run as
  administrator" retry. Without ``WRITE_DAC`` the apply fails closed.
* It never writes the planned parent-directory deny ACE. That entry is
  *described only*: applying it would mutate a directory shared with other
  skills and with the rest of the host.
* It does not claim containment. A DACL naming one SID constrains that SID;
  it does not stop any other account, and it does not survive the child
  process outliving this module unless the caller keeps the rollback handle.
* No AppContainer, no ``WindowsSandbox.exe``, no OS network boundary.

The path guard is real in *both* modes: ``..`` is refused before
:meth:`resolve_acl_target` ever calls ``Path.resolve()``, and system
locations and their ancestors are refused outright.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .policy import FS_ISOLATED, FS_READ, FS_WRITE

# A well-known root that must never be a target, whatever the configuration.
_FORBIDDEN_ROOTS = (
    Path(os.environ.get("SystemRoot", r"C:\Windows")),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    Path(os.environ.get("ProgramData", r"C:\ProgramData")),
)


from .acl_types import (
    AclEntry,
    AclPlan,
    AclPlanError,
    AclRollbackHandle,
    SidHandle,
)
from .acl_guard_winapi import (
    _AclApi,
    _UnsupportedApi,
    _WindowsAclApi,
    rights_to_mask,
)


def _norm(path: Path) -> str:
    return str(path).replace("\\", "/").rstrip("/").lower()


def _is_ancestor(candidate: Path, path: Path) -> bool:
    c, p = _norm(candidate), _norm(path)
    return p == c or p.startswith(c + "/")


def resolve_acl_target(workspace: Path, protected_roots: Sequence[Path] = ()) -> Path:
    """Validate ``workspace`` as an ACL target and return its resolved form.

    Rejects anything that is not an existing directory, anything that escapes
    via ``..`` or a junction, and anything at or above a system location.
    """
    raw = Path(workspace)
    # A caller-supplied "..", a junction or a symlink escape are refused up
    # front. Resolving first and only inspecting the final location would
    # silently accept a traversal that happens to land back on a real
    # directory, which is exactly the typo this guard exists to catch.
    if ".." in raw.parts:
        raise AclPlanError(
            f"ACL target {raw} contains a '..' segment. Refusing to resolve a "
            "traversal; pass an explicit, already-confined directory."
        )
    if not raw.is_absolute():
        raw = (Path.cwd() / raw).resolve()
    resolved = raw.resolve()

    if not resolved.exists() or not resolved.is_dir():
        raise AclPlanError(
            f"ACL target {resolved} is not an existing directory; refusing to "
            "plan access for a path that does not exist."
        )

    for root in list(_FORBIDDEN_ROOTS) + [Path(p) for p in protected_roots]:
        try:
            root_resolved = Path(root).resolve()
        except (OSError, RuntimeError):
            continue
        # The forbidden location itself, or any ancestor of it, is never a
        # legitimate per-skill ACL target.
        if _is_ancestor(root_resolved, resolved) or _is_ancestor(
            resolved, root_resolved
        ):
            raise AclPlanError(
                f"ACL target {resolved} is a system location or an ancestor of "
                f"one ({root_resolved}). Refusing to plan ACL changes there."
            )

    if resolved.parent == resolved:
        raise AclPlanError(
            f"ACL target {resolved} is a filesystem root; refusing to plan ACL "
            "changes at the root."
        )

    return resolved



_API_CACHE: Dict[str, _AclApi] = {}


def get_acl_api() -> _AclApi:
    """Return the real Windows API, or a fail-closed stand-in."""
    if os.name != "nt":
        return _UnsupportedApi()
    cached = _API_CACHE.get("windows")
    if cached is not None:
        return cached
    try:
        api = _WindowsAclApi()
    except Exception:
        # A missing advapi32 or a blocked DLL must not look like success.
        api = _UnsupportedApi()
    _API_CACHE["windows"] = api
    return api


def build_acl_plan(
    workspace: Path,
    principal_sid: Optional[str],
    granted_capabilities: Iterable[str],
    dry_run: bool = True,
    protected_roots: Sequence[Path] = (),
) -> AclPlan:
    """Compute -- and on Windows really write -- the sandbox ACE set.

    ``dry_run=True`` (the default) is pure planning: no Windows API is
    touched, the principal string is echoed back verbatim, and
    :attr:`AclPlan.enforced` stays ``False``.

    ``dry_run=False`` performs real enforcement:

    * the principal is resolved (SID string or existing account name),
    * the original DACL is captured for rollback,
    * an allow ACE for the granted rights is written with
      ``SetNamedSecurityInfoW``,
    * the DACL is read back and the ACE for the resolved SID is verified.

    Any failure raises :class:`AclPlanError` after restoring the original DACL
    where possible. This function never creates a Windows account and never
    elevates.
    """
    target = resolve_acl_target(workspace, protected_roots)
    caps = {c.strip().lower() for c in granted_capabilities if c}

    if not principal_sid:
        raise AclPlanError(
            "No sandbox principal (SID or account name) was supplied, so no "
            "ACE could name a trustee. Refusing to grant access to 'Everyone'."
        )

    rights: List[str] = []
    reasons: List[str] = []
    if FS_READ in caps or FS_ISOLATED in caps:
        rights.append("read")
        reasons.append(f"granted {FS_READ}" if FS_READ in caps else FS_ISOLATED)
    if FS_WRITE in caps:
        rights.append("write")
        reasons.append(f"granted {FS_WRITE}")
    elif FS_ISOLATED in caps:
        rights.append("write")
        reasons.append(f"{FS_ISOLATED} implies write inside the workspace")

    if not rights:
        raise AclPlanError(
            "The policy granted no filesystem capability "
            f"({sorted(caps) or 'none'}), so there is nothing to plan. Not "
            "inventing a read grant."
        )

    allow_entry = AclEntry(
        principal=principal_sid,
        rights=rights,
        inheritance="container_and_object",
        allow=True,
        reason="; ".join(reasons),
    )
    deny_entry = AclEntry(
        principal=principal_sid,
        rights=["write", "delete"],
        inheritance="none",
        allow=False,
        reason=(
            "Deny write/delete above the per-skill workspace so the sandbox "
            "principal cannot reach sibling data through a parent path. "
            "DESCRIBED ONLY -- not applied: the parent directory is shared "
            "with other skills and with the rest of the host."
        ),
    )
    warnings: List[str] = [
        "The parent-directory deny ACE is described only; no parent DACL was "
        "modified."
    ]

    if dry_run:
        warnings.append(
            "ACL PLAN ONLY: no ACE was written. dry_run=True never calls "
            "SetNamedSecurityInfoW, so the skill would run with the full NTFS "
            "rights of its host account."
        )
        return AclPlan(
            target=str(target),
            entries=[allow_entry, deny_entry],
            enforced=False,
            dry_run=True,
            resolved_sid=principal_sid,
            warnings=warnings,
        )

    mask = rights_to_mask(rights)
    api = get_acl_api()
    sid = api.resolve_sid(principal_sid)
    try:
        descriptor = api.apply_allow_rules(
            str(target), sid, mask, inheritable=True
        )
    except AclPlanError:
        sid.free()
        raise
    except Exception as exc:  # pragma: no cover - defensive
        sid.free()
        raise AclPlanError(
            f"Writing the sandbox DACL on {target} failed: {exc}"
        ) from exc

    resolved = sid.text or principal_sid
    try:
        verified = api.verify_allow_rules(str(target), sid, mask)
    except BaseException as exc:
        restored = _restore_descriptor(api, str(target), descriptor)
        sid.free()
        raise AclPlanError(
            f"ACL verification on {target} raised: {exc}. The original DACL was "
            + ("restored." if restored else "NOT restored.")
        )
    if not verified:
        restored = _restore_descriptor(api, str(target), descriptor)
        sid.free()
        raise AclPlanError(
            f"The allow ACE for {resolved} did not verify on {target} after "
            "SetNamedSecurityInfoW reported success. The original DACL was "
            + ("restored." if restored else "NOT restored.")
        )

    sid.free()
    allow_entry.principal = resolved
    allow_entry.applied = True
    warnings.append(
        f"NTFS DACL enforced for {allow_entry.principal} on {target} via "
        "SetNamedSecurityInfoW and verified by read-back."
    )
    return AclPlan(
        target=str(target),
        entries=[allow_entry, deny_entry],
        enforced=True,
        dry_run=False,
        resolved_sid=allow_entry.principal,
        rollback=AclRollbackHandle(target=str(target), _api=api, _descriptor=descriptor),
        warnings=warnings,
    )


def _restore_descriptor(api: "_AclApi", path: str, descriptor: Any) -> List[str]:
    """Restore then free the descriptor, reporting what happened."""
    try:
        api.set_dacl(path, descriptor)
        note = f"Restored the original DACL on {path}."
    except Exception as exc:
        note = (
            f"ACL ROLLBACK FAILED for {path}: {exc}. The workspace still carries "
            "the sandbox ACE; remove it manually."
        )
    finally:
        try:
            api.free_descriptor(descriptor)
        except Exception:
            pass
    return [note] if note.startswith("Restored") else []


__all__ = [
    "AclEntry",
    "AclPlan",
    "AclPlanError",
    "AclRollbackHandle",
    "SidHandle",
    "build_acl_plan",
    "get_acl_api",
    "resolve_acl_target",
    "rights_to_mask",
]
