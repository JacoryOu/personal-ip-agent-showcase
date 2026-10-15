"""Process-wide catalogue of declared high-risk workflow actions."""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from app.core.workflow_permissions.audit import (
    AuditDecision,
    AuditRecord,
    _resolve_sink,
)
from app.core.workflow_permissions.declarations import PermissionAction

class _Registry:
    """Process-wide catalogue of declared high-risk workflow actions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._actions: Dict[str, PermissionAction] = {}

    def register(self, declaration: PermissionAction) -> PermissionAction:
        with self._lock:
            self._actions[declaration.action] = declaration
        return declaration

    def get(self, action: str) -> Optional[PermissionAction]:
        with self._lock:
            return self._actions.get(action)

    def matches(self, declaration: PermissionAction) -> bool:
        """True only when the declaration is byte-for-byte the registered one.

        A caller may not hand-craft a lower-risk version of a known action (or a
        brand-new action that was never declared) and expect it to be trusted:
        declarations are only trusted when they come from :func:`declare_action`.
        """
        with self._lock:
            canonical = self._actions.get(declaration.action)
        if canonical is None:
            return False
        return canonical.model_dump(mode="json") == declaration.model_dump(mode="json")

    def names(self) -> List[str]:
        with self._lock:
            return sorted(self._actions)


REGISTRY = _Registry()


def declare_action(action: PermissionAction) -> PermissionAction:
    """Register an action declaration. Use at import time of the owning module."""
    return REGISTRY.register(action)


def registered_actions() -> List[str]:
    return REGISTRY.names()


def query_audit(
    *,
    action: Optional[str] = None,
    actor_id: Optional[str] = None,
    decision: Optional[AuditDecision] = None,
) -> List[AuditRecord]:
    """Query the audit trail. Read-only."""
    records = _resolve_sink().records()
    out = []
    for record in records:
        if action is not None and record.action != action:
            continue
        if actor_id is not None and record.actor_id != actor_id:
            continue
        if decision is not None and record.decision != decision:
            continue
        out.append(record)
    return out
