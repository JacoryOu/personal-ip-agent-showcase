"""Audit records and sinks, including the append-only JSONL hash-chained sink.

HONESTY: the JSONL chain detects accidental edit or truncation and orders the
records, but it is **not** tamper-proof -- anyone able to rewrite the file and
recompute the chain defeats it. A signed or remote sink is not implemented.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.workflow_permissions.vocabulary import (
    ENV_AUDIT_PATH,
    AuditDecision,
    RiskLevel,
    WorkflowMode,
)

logger = logging.getLogger(__name__)

class AuditRecord(BaseModel):
    id: str
    when: str
    actor_id: str
    action: str
    permissions: List[str]
    risk: RiskLevel
    # Stored as a plain string (not the enum) so that an *unknown* mode can
    # still be recorded faithfully instead of failing while being audited.
    mode: str
    decision: AuditDecision
    reason: str
    detail: Dict[str, Any] = Field(default_factory=dict)
    prev_hash: str = ""
    hash: str = ""


class AuditSink(ABC):
    """Append-only audit destination. Business code never writes here directly."""

    @abstractmethod
    def append(self, record: AuditRecord) -> None:
        ...

    @abstractmethod
    def records(self) -> List[AuditRecord]:
        ...


class InMemoryAuditSink(AuditSink):
    """Process-local sink. Intended for tests and single-process dev runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[AuditRecord] = []

    def append(self, record: AuditRecord) -> None:
        with self._lock:
            record.prev_hash = self._records[-1].hash if self._records else ""
            record.hash = _record_hash(record)
            self._records.append(record)

    def records(self) -> List[AuditRecord]:
        with self._lock:
            return list(self._records)


class JsonlAuditSink(AuditSink):
    """Append-only JSONL sink with a hash chain and a process-local lock.

    HONESTY: the chain detects *accidental* edit or truncation and orders the
    records, but it is not tamper-proof -- anyone able to rewrite the file can
    recompute the chain. A signed or remote sink is **not implemented**.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    @property
    def path(self) -> str:
        return self._path

    def append(self, record: AuditRecord) -> None:
        # The lock is re-entrant because linking the hash chain requires reading
        # the existing log while the append lock is held; a plain Lock would
        # deadlock here (append -> records -> Lock).
        with self._lock:
            existing = self._read_records_unlocked()
            record.prev_hash = existing[-1].hash if existing else ""
            record.hash = _record_hash(record)
            line = record.model_dump_json()
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())

    def records(self) -> List[AuditRecord]:
        with self._lock:
            return self._read_records_unlocked()

    def _read_records_unlocked(self) -> List[AuditRecord]:
        """Read the log. Caller must already hold ``self._lock``.

        A torn final line (crash mid-write) must not hide the earlier records,
        so unparseable lines are skipped with a warning. Honest caveat: a
        corrupted *middle* record is skipped too, and ``verify_chain`` then
        reports a broken chain rather than silently succeeding.
        """
        if not os.path.exists(self._path):
            return []
        out: List[AuditRecord] = []
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(AuditRecord.model_validate_json(line))
                except Exception:  # a torn final line must not hide the rest
                    logger.warning("Skipping unparseable workflow audit line")
        return out

    def verify_chain(self) -> bool:
        prev = ""
        for record in self.records():
            if record.prev_hash != prev or _record_hash(record) != record.hash:
                return False
            prev = record.hash
        return True


def _record_hash(record: AuditRecord) -> str:
    payload = record.model_dump(mode="json")
    payload.pop("hash", None)
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _build_record(
    *,
    actor_id: str,
    action: str,
    permissions: List[str],
    risk: RiskLevel,
    mode: WorkflowMode,
    decision: AuditDecision,
    reason: str,
    detail: Optional[Dict[str, Any]] = None,
) -> AuditRecord:
    record = AuditRecord(
        id=str(uuid.uuid4()),
        when=datetime.now(timezone.utc).isoformat(),
        actor_id=actor_id,
        action=action,
        permissions=list(permissions),
        risk=risk,
        mode=getattr(mode, "value", mode),
        decision=decision,
        reason=reason,
        detail=dict(detail or {}),
    )
    # prev_hash / hash are assigned by the sink at append time so that the
    # chain links to the record that is actually physically preceding this one.
    return record


_sink_lock = threading.Lock()
_sink: Optional[AuditSink] = None


def _resolve_sink() -> AuditSink:
    """Resolve the process-wide audit sink. Freezing happens on first use."""
    global _sink
    if _sink is None:
        with _sink_lock:
            if _sink is None:
                path = os.environ.get(ENV_AUDIT_PATH, "").strip()
                _sink = JsonlAuditSink(path) if path else InMemoryAuditSink()
    return _sink


def _reset_sink_for_tests(sink: Optional[AuditSink]) -> None:
    """Test-only seam. Not part of the supported production surface."""
    global _sink
    with _sink_lock:
        _sink = sink


def _append_audit(record: AuditRecord) -> None:
    _resolve_sink().append(record)
