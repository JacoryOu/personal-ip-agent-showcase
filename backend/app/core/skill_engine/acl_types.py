"""Shared, side-effect-free ACL data types.

Split out of :mod:`acl_guard` so both the planner/enforcer facade and the
Windows API bindings can depend on the same types without importing each
other. Nothing in this module touches ctypes or the Win32 API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


class AclPlanError(ValueError):
    """Raised when a safe ACL plan cannot be produced or enforced."""


@dataclass
class AclEntry:
    principal: str
    rights: List[str]
    inheritance: str = "container_and_object"
    allow: bool = True
    applied: bool = False
    reason: str = ""

    def describe(self) -> dict:
        return {
            "principal": self.principal,
            "rights": list(self.rights),
            "inheritance": self.inheritance,
            "allow": self.allow,
            "applied": self.applied,
            "reason": self.reason,
        }


@dataclass
class AclPlan:
    target: str
    entries: List[AclEntry] = field(default_factory=list)
    # True only when SetNamedSecurityInfoW succeeded AND the DACL was read back
    # and verified to contain the expected allow ACE for the target SID.
    enforced: bool = False
    dry_run: bool = True
    resolved_sid: Optional[str] = None
    rollback: Optional["AclRollbackHandle"] = field(default=None, repr=False)
    warnings: List[str] = field(default_factory=list)

    def describe(self) -> dict:
        return {
            "target": self.target,
            "entries": [e.describe() for e in self.entries],
            "enforced": self.enforced,
            "dry_run": self.dry_run,
            "resolved_sid": self.resolved_sid,
            "warnings": list(self.warnings),
        }

    def restore(self) -> List[str]:
        """Put the original DACL back. Never raises; returns human notes."""
        if self.rollback is None:
            return []
        return self.rollback.restore()


@dataclass
class AclRollbackHandle:
    """Owns the saved original security descriptor until it is restored."""

    target: str
    _api: Any = field(repr=False)
    _descriptor: Any = field(repr=False)
    _consumed: bool = field(default=False, repr=False)

    def restore(self) -> List[str]:
        notes: List[str] = []
        if self._consumed:
            return ["ACL rollback was already performed; nothing to restore."]
        self._consumed = True
        try:
            self._api.set_dacl(self.target, self._descriptor)
            notes.append(f"Restored the original DACL on {self.target}.")
        except AclPlanError as exc:
            notes.append(
                f"ACL ROLLBACK FAILED for {self.target}: {exc} The workspace now "
                "carries the sandbox ACE set; remove it manually (icacls "
                f'"{self.target}" /reset) before reusing this directory.'
            )
        finally:
            self._api.free_descriptor(self._descriptor)
            self._descriptor = None
        return notes

    def __del__(self) -> None:  # pragma: no cover - best-effort cleanup
        if not self._consumed and self._descriptor is not None:
            try:
                self._api.free_descriptor(self._descriptor)
            except Exception:
                pass
            self._descriptor = None


class SidHandle:
    """An owned SID pointer plus its string form."""

    def __init__(self, pointer: Any, text: str, free) -> None:
        self._pointer = pointer
        self.text = text
        self._free = free

    @property
    def pointer(self):
        return self._pointer

    def free(self) -> None:
        if self._pointer is not None:
            self._free(self._pointer)
            self._pointer = None

    def __del__(self) -> None:  # pragma: no cover - best-effort cleanup
        try:
            self.free()
        except Exception:
            pass


__all__ = [
    "AclEntry",
    "AclPlan",
    "AclPlanError",
    "AclRollbackHandle",
    "SidHandle",
]
