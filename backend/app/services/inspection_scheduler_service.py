"""Public facade for the inspection scheduler.

The implementation lives in focused sibling modules:

* :mod:`app.services.inspection_scheduler_helpers` - pure helpers
* :mod:`app.services.inspection_scheduler_state` - per-user state
* :mod:`app.services.inspection_scheduler_wheels` - inspection wheels
* :mod:`app.services.inspection_scheduler_briefing` - daily briefing
* :mod:`app.services.inspection_scheduler_runtime` - cycle / loop, `..._status` - status / quota

Every public method keeps the exact signature and behaviour it had when the implementation lived here.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import Session

# Re-exported for backwards compatibility: callers and tests monkeypatch
# `inspection_scheduler_service.engine` / `.get_skill_manager`, and the
# split modules resolve these through the facade at call time.
from app.core.db import engine
from app.core.skill_engine import get_skill_manager

from app.models.material import Material
from app.models.scheduler_state import SchedulerUserState
from app.schemas.scheduler_schemas import SchedulerSettings
from app.services.inspection_scheduler_helpers import DEFAULT_SCOPE

import app.services.inspection_scheduler_state as _state
import app.services.inspection_scheduler_wheels as _wheels
import app.services.inspection_scheduler_briefing as _briefing
import app.services.inspection_scheduler_runtime as _runtime
import app.services.inspection_scheduler_status as _status


class InspectionSchedulerService:
    """
    Periodic inspection scheduler.

    User-facing state (settings, briefing dismissed date, last quota decision,
    last execution summary) is keyed per user so one authenticated caller can
    never read or overwrite another caller's state.

    The background loop keeps using the process-level ``DEFAULT_SCOPE`` entry as
    its own scheduler configuration; it is *not* shared with any user scope.
    For a *real* user the four state items are persisted in the
    ``scheduler_user_states`` table, so they survive a restart and are
    consistent across workers. The background loop's ``DEFAULT_SCOPE``
    configuration stays in memory: it belongs to no user row, and writing a
    row without a real user would fabricate an identity.
    """

    def __init__(self):
        self.settings: SchedulerSettings = SchedulerSettings()
        self._settings_by_user: Dict[str, SchedulerSettings] = {
            DEFAULT_SCOPE: self.settings
        }
        self._loop_task: Optional[asyncio.Task] = None
        self._last_run_time: Optional[datetime] = None
        self._last_execution_summary: Optional[Dict[str, Any]] = None
        self._is_inspecting: bool = False
        self._dismissed_date: Optional[str] = None
        self._last_quota_decision: Optional[Dict[str, Any]] = None
        self._summary_by_user: Dict[str, Dict[str, Any]] = {}
        self._dismissed_by_user: Dict[str, Optional[str]] = {}
        self._quota_decision_by_user: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _scope(user_id: Optional[str | uuid.UUID]) -> str:
        return _state._scope(user_id)

    @staticmethod
    def _settings_from_payload(payload: Optional[Dict[str, Any]]) -> SchedulerSettings:
        return _state._settings_from_payload(payload)

    @staticmethod
    def _load_user_state(sess: Session, uid: uuid.UUID) -> Optional[SchedulerUserState]:
        return _state._load_user_state(sess, uid)

    def _get_or_create_user_state(
        self,
        sess: Session,
        uid: uuid.UUID
    ) -> SchedulerUserState:
        return _state._get_or_create_user_state(self, sess, uid)

    def _read_dismissed_date(
        self,
        sess: Session,
        uid: uuid.UUID,
        fallback: Optional[str] = None
    ) -> Optional[str]:
        return _state._read_dismissed_date(self, sess, uid, fallback)

    def _read_state_json(
        self,
        sess: Session,
        uid: uuid.UUID,
        field: str
    ) -> Optional[Dict[str, Any]]:
        return _state._read_state_json(self, sess, uid, field)

    def _write_state_field(
        self,
        sess: Session,
        uid: uuid.UUID,
        field: str,
        value: Optional[Dict[str, Any]]
    ) -> None:
        return _state._write_state_field(self, sess, uid, field, value)

    def get_settings(
        self,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None
    ) -> SchedulerSettings:
        return _state.get_settings(self, user_id, session)

    def update_settings(
        self,
        updates: Dict[str, Any],
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None
    ) -> SchedulerSettings:
        return _state.update_settings(self, updates, user_id, session)

    def calculate_next_run_time(self) -> Optional[datetime]:
        return _runtime.calculate_next_run_time(self)

    def run_wheel_1(
        self,
        session: Session,
        user_id: Optional[str | uuid.UUID] = None,
        custom_settings: Optional[SchedulerSettings] = None
    ) -> List[Material]:
        return _wheels.run_wheel_1(self, session, user_id, custom_settings)

    def run_wheel_2(
        self,
        session: Session,
        user_id: Optional[str | uuid.UUID] = None,
        custom_settings: Optional[SchedulerSettings] = None
    ) -> List[Material]:
        return _wheels.run_wheel_2(self, session, user_id, custom_settings)

    def run_inspection_cycle(
        self,
        session: Optional[Session] = None,
        user_id: Optional[str | uuid.UUID] = None
    ) -> Dict[str, Any]:
        return _runtime.run_inspection_cycle(self, session, user_id)

    def get_today_briefing(
        self,
        session: Optional[Session] = None,
        user_id: Optional[str | uuid.UUID] = None
    ) -> Dict[str, Any]:
        return _briefing.get_today_briefing(self, session, user_id)

    def confirm_briefing_into_vault(
        self,
        session: Optional[Session] = None,
        user_id: Optional[str | uuid.UUID] = None
    ) -> Dict[str, Any]:
        return _briefing.confirm_briefing_into_vault(self, session, user_id)

    def mark_briefing_read(
        self,
        date_str: Optional[str] = None,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        return _briefing.mark_briefing_read(self, date_str, user_id, session)

    def get_status(
        self,
        session: Optional[Session] = None,
        user_id: Optional[str | uuid.UUID] = None
    ) -> Dict[str, Any]:
        return _status.get_status(self, session, user_id)

    def _calculate_next_run_time(
        self,
        settings: Optional[SchedulerSettings] = None
    ) -> Optional[datetime]:
        return _status._calculate_next_run_time(self, settings)

    def get_quota_status(
        self,
        session: Optional[Session] = None,
        user_id: Optional[str | uuid.UUID] = None
    ) -> Dict[str, Any]:
        return _status.get_quota_status(self, session, user_id)

    def set_quota_grant(
        self,
        session: Optional[Session] = None,
        user_id: Optional[str | uuid.UUID] = None,
        **updates: Any
    ) -> Dict[str, Any]:
        return _status.set_quota_grant(self, session, user_id, **updates)

    async def _scheduler_loop(self):
        return await _runtime._scheduler_loop(self)

    async def start(self):
        return await _runtime.start(self)

    async def stop(self):
        return await _runtime.stop(self)


# Global singleton instance
inspection_scheduler = InspectionSchedulerService()
