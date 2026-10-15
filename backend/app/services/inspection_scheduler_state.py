"""Per-user scheduler settings and persisted scheduler state."""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import Optional
from app.schemas.scheduler_schemas import SchedulerSettings
from app.models.scheduler_state import SchedulerUserState
from sqlmodel import Session
from datetime import datetime
import logging
from sqlmodel import select
from datetime import timezone
import uuid
from app.services.inspection_scheduler_helpers import (
    _facade_engine,
    DEFAULT_SCOPE,
    _parse_uid,
)

logger = logging.getLogger(__name__)

def _scope(user_id: Optional[str | uuid.UUID]) -> str:
    uid = _parse_uid(user_id)
    return str(uid) if uid else DEFAULT_SCOPE


def _settings_from_payload(payload: Optional[Dict[str, Any]]) -> SchedulerSettings:
    """Rebuild SchedulerSettings from a persisted dict, ignoring junk keys."""
    if not payload:
        return SchedulerSettings()
    allowed = set(SchedulerSettings.model_fields.keys())
    clean = {k: v for k, v in payload.items() if k in allowed}
    try:
        return SchedulerSettings(**clean)
    except Exception:
        logger.warning("Discarding unparsable persisted scheduler settings")
        return SchedulerSettings()


def _load_user_state(sess: Session, uid: uuid.UUID) -> Optional[SchedulerUserState]:
    return sess.exec(
        select(SchedulerUserState).where(SchedulerUserState.user_id == uid)
    ).first()


def _get_or_create_user_state(self, sess: Session, uid: uuid.UUID) -> SchedulerUserState:
    row = _load_user_state(sess, uid)
    if row is None:
        row = SchedulerUserState(user_id=uid)
        sess.add(row)
        sess.commit()
        sess.refresh(row)
    return row


def _read_dismissed_date(
    self,
    sess: Session,
    uid: uuid.UUID,
    fallback: Optional[str] = None,
) -> Optional[str]:
    row = _load_user_state(sess, uid)
    if row is None:
        return fallback
    return row.dismissed_date if row.dismissed_date else fallback


def _read_state_json(
    self,
    sess: Session,
    uid: uuid.UUID,
    field: str,
) -> Optional[Dict[str, Any]]:
    row = _load_user_state(sess, uid)
    if row is None:
        return None
    value = getattr(row, field, None)
    return value if isinstance(value, dict) and value else None


def _write_state_field(
    self,
    sess: Session,
    uid: uuid.UUID,
    field: str,
    value: Optional[Dict[str, Any]],
) -> None:
    row = _get_or_create_user_state(self, sess, uid)
    setattr(row, field, value or {})
    row.updated_at = datetime.now(timezone.utc)
    sess.add(row)
    sess.commit()


def get_settings(
    self,
    user_id: Optional[str | uuid.UUID] = None,
    session: Optional[Session] = None,
) -> SchedulerSettings:
    uid = _parse_uid(user_id)
    if uid is None:
        return self._settings_by_user.get(DEFAULT_SCOPE, SchedulerSettings())

    def _execute(sess: Session) -> SchedulerSettings:
        row = _load_user_state(sess, uid)
        if row is None:
            return SchedulerSettings()
        return _settings_from_payload(row.settings)

    if session is not None:
        return _execute(session)
    with Session(_facade_engine()) as s:
        return _execute(s)


def update_settings(
    self,
    updates: Dict[str, Any],
    user_id: Optional[str | uuid.UUID] = None,
    session: Optional[Session] = None,
) -> SchedulerSettings:
    uid = _parse_uid(user_id)
    if uid is None:
        # Background-loop / unknown scope: process-level configuration only.
        current = self._settings_by_user.get(DEFAULT_SCOPE, self.settings)
        current_data = current.model_dump()
        for k, v in updates.items():
            if v is not None and k in current_data:
                current_data[k] = v
        updated = SchedulerSettings(**current_data)
        self._settings_by_user[DEFAULT_SCOPE] = updated
        self.settings = updated
        return updated

    def _execute(sess: Session) -> SchedulerSettings:
        row = _get_or_create_user_state(self, sess, uid)
        current_data = _settings_from_payload(row.settings).model_dump()
        for k, v in updates.items():
            if v is not None and k in current_data:
                current_data[k] = v
        updated = SchedulerSettings(**current_data)
        row.settings = updated.model_dump()
        row.updated_at = datetime.now(timezone.utc)
        sess.add(row)
        sess.commit()
        sess.refresh(row)
        return updated

    if session is not None:
        return _execute(session)
    with Session(_facade_engine()) as s:
        return _execute(s)
