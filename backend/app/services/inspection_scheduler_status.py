"""Scheduler status reporting, next-run calculation and external-call quota."""

from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Dict
from typing import Optional

from sqlmodel import Session

from app.services.cognitive_service import CognitiveService
from app.schemas.scheduler_schemas import SchedulerSettings
from app.services.inspection_scheduler_helpers import _facade_engine, _parse_uid
from app.services.inspection_quota_service import get_status as quota_get_status
from app.services.inspection_quota_service import set_grant as quota_set_grant
import logging

import app.services.inspection_scheduler_briefing as _briefing
import app.services.inspection_scheduler_state as _state

logger = logging.getLogger(__name__)


def get_status(
    self,
    session: Optional[Session] = None,
    user_id: Optional[str | uuid.UUID] = None,
) -> Dict[str, Any]:
    """Returns the current status of the background inspection scheduler."""
    scope = _state._scope(user_id)
    uid = _parse_uid(user_id)
    user_settings = _state.get_settings(self, user_id, session=session)
    next_run = _calculate_next_run_time(self, user_settings)
    briefing = _briefing.get_today_briefing(self, session=session, user_id=user_id)
    unread_count = briefing["total_items"] if briefing["unread"] else 0

    def _read_all(sess: Session) -> tuple:
        if uid is None:
            return (
                self._summary_by_user.get(scope),
                self._quota_decision_by_user.get(scope),
            )
        return (
            _state._read_state_json(self, sess, uid, "last_summary"),
            _state._read_state_json(self, sess, uid, "quota_decision"),
        )

    if session is not None:
        last_summary, last_quota_decision = _read_all(session)
    else:
        with Session(_facade_engine()) as s:
            last_summary, last_quota_decision = _read_all(s)

    return {
        "running": self._loop_task is not None and not self._loop_task.done(),
        "enabled": user_settings.enabled,
        "interval_hours": user_settings.interval_hours,
        "daily_briefing_time": user_settings.daily_briefing_time,
        "next_run_time": next_run.isoformat() if next_run else None,
        "last_run_time": self._last_run_time.isoformat() if self._last_run_time else None,
        "last_execution_summary": last_summary,
        "settings": user_settings.model_dump(),
        "unread_briefing_count": unread_count,
        "inspection_quota": get_quota_status(self, session=session, user_id=user_id),
        "last_quota_decision": last_quota_decision,
    }


def _calculate_next_run_time(
    self, settings: Optional[SchedulerSettings] = None
) -> Optional[datetime]:
    cfg = settings or self.settings
    if not cfg.enabled:
        return None
    if cfg.daily_briefing_time and ":" in cfg.daily_briefing_time:
        try:
            hh, mm = map(int, cfg.daily_briefing_time.split(":")[:2])
            now_local = datetime.now().astimezone()
            candidate = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if candidate <= now_local:
                candidate += timedelta(days=1)
            return candidate
        except (ValueError, TypeError):
            logger.warning("Invalid daily_briefing_time: %r", cfg.daily_briefing_time)
    if self._last_run_time:
        return self._last_run_time + timedelta(hours=cfg.interval_hours)
    return datetime.now(timezone.utc) + timedelta(hours=cfg.interval_hours)


def get_quota_status(
    self,
    session: Optional[Session] = None,
    user_id: Optional[str | uuid.UUID] = None,
) -> Dict[str, Any]:
    """Return the persisted external-call budget for the acting user."""
    def _execute(sess: Session) -> Dict[str, Any]:
        uid = _parse_uid(user_id)
        if uid is None:
            uid = CognitiveService.get_or_create_default_user(sess).id
        return quota_get_status(sess, uid)

    if session:
        return _execute(session)
    with Session(_facade_engine()) as s:
        return _execute(s)


def set_quota_grant(
    self,
    session: Optional[Session] = None,
    user_id: Optional[str | uuid.UUID] = None,
    **updates: Any,
) -> Dict[str, Any]:
    """Grant / revoke unattended inspection external-call authorization."""
    def _execute(sess: Session) -> Dict[str, Any]:
        uid = _parse_uid(user_id)
        if uid is None:
            uid = CognitiveService.get_or_create_default_user(sess).id
        return quota_set_grant(sess, uid, **updates)

    if session:
        return _execute(session)
    with Session(_facade_engine()) as s:
        return _execute(s)
