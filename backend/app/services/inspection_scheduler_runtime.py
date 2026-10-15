"""Inspection cycle orchestration and the background scheduler loop."""

from __future__ import annotations

from typing import Any
from app.services.cognitive_service import CognitiveService
from typing import Dict
from typing import List
from app.models.material import Material
from typing import Optional
from sqlmodel import Session
import asyncio
from datetime import datetime
import logging
from app.services.inspection_quota_service import get_quota as quota_get_quota
from app.services.inspection_quota_service import (
    record_error as quota_record_error,
)
from app.services.inspection_quota_service import reset_run as quota_reset_run
import time
from datetime import timedelta
from datetime import timezone
import uuid
from app.services.inspection_scheduler_helpers import (
    _facade_engine,
    DEFAULT_SCOPE,
    _parse_uid,
)
import app.services.inspection_scheduler_state as _state
import app.services.inspection_scheduler_wheels as _wheels

logger = logging.getLogger(__name__)

def calculate_next_run_time(self) -> Optional[datetime]:
    if not self.settings.enabled:
        return None
    now = datetime.now(timezone.utc)

    # 1. Interval-based next time
    if self._last_run_time:
        interval_next = self._last_run_time + timedelta(hours=self.settings.interval_hours)
        if interval_next <= now:
            interval_next = now + timedelta(hours=self.settings.interval_hours)
    else:
        interval_next = now + timedelta(hours=self.settings.interval_hours)

    # 2. Daily briefing scheduled time
    daily_next = None
    if self.settings.daily_briefing_time and ":" in self.settings.daily_briefing_time:
        try:
            hh, mm = map(int, self.settings.daily_briefing_time.split(":")[:2])
            candidate = datetime(now.year, now.month, now.day, hh, mm, tzinfo=timezone.utc)
            if candidate <= now:
                candidate += timedelta(days=1)
            daily_next = candidate
        except Exception:
            pass

    if daily_next and daily_next < interval_next:
        return daily_next
    return interval_next


def run_inspection_cycle(
    self,
    session: Optional[Session] = None,
    user_id: Optional[str | uuid.UUID] = None,
) -> Dict[str, Any]:
    """Runs a complete dual-wheel inspection cycle."""
    if self._is_inspecting:
        return {
            "success": False,
            "message": "巡检正在进行中，请稍候...",
            "wheel1_new_topics": 0,
            "wheel2_new_blueprints": 0,
            "total_new_items": 0,
            "duration_ms": 0,
        }

    self._is_inspecting = True
    start_time = time.perf_counter()

    def _do_cycle(s: Session) -> Dict[str, Any]:
        cycle_uid = _parse_uid(user_id)
        if cycle_uid is None:
            cycle_uid = CognitiveService.get_or_create_default_user(s).id

        # A new cycle resets the per-run budget before anything is consumed.
        try:
            quota_reset_run(quota_get_quota(s, cycle_uid))
            s.commit()
        except Exception:
            logger.exception("Failed to reset inspection quota for user=%s", cycle_uid)

        denied_reason: Optional[str] = None
        w1_items: List[Material] = []
        try:
            w1_items = _wheels.run_wheel_1(self, s, user_id=cycle_uid)
            last_decision = _state._read_state_json(self, s, cycle_uid, "quota_decision")
            if not w1_items and last_decision and not last_decision.get("allowed"):
                denied_reason = last_decision.get("reason")
        except Exception as exc:
            logger.exception("Wheel1 inspection failed for user=%s", cycle_uid)
            quota_record_error(s, cycle_uid, f"wheel1 failed: {exc}")
            denied_reason = "wheel1_error"

        w2_items: List[Material] = []
        if denied_reason is None:
            try:
                w2_items = _wheels.run_wheel_2(self, s, user_id=cycle_uid)
            except Exception as exc:
                logger.exception("Wheel2 inspection failed for user=%s", cycle_uid)
                quota_record_error(s, cycle_uid, f"wheel2 failed: {exc}")
                denied_reason = "wheel2_error"
        else:
            # Quota / pre-authorization denied: the whole unattended cycle is
            # skipped so that neither wheel performs an external call.
            logger.warning(
                "Skipping wheel2 for user=%s: inspection quota denied (%s)",
                cycle_uid,
                denied_reason,
            )

        duration_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        now = datetime.now(timezone.utc)
        self._last_run_time = now

        success = denied_reason is None
        if denied_reason:
            message = (
                f"巡检已跳过外部抓取（原因：{denied_reason}）。"
                "请在巡检配额中预授权后再试。"
            )
        else:
            message = f"巡检完成：新增 {len(w1_items)} 条全网热点，{len(w2_items)} 篇对标爆款已静默提取骨架"

        summary = {
            "success": success,
            "wheel1_new_topics": len(w1_items),
            "wheel2_new_blueprints": len(w2_items),
            "total_new_items": len(w1_items) + len(w2_items),
            "duration_ms": duration_ms,
            "message": message,
            "denied_reason": denied_reason,
            "executed_at": now.isoformat(),
        }
        self._last_execution_summary = summary
        try:
            _state._write_state_field(self, s, cycle_uid, "last_summary", summary)
        except Exception:
            logger.exception("Failed to persist execution summary for user=%s", cycle_uid)
        # New items arrived, reset dismissed date so user sees unread notification
        if (len(w1_items) + len(w2_items)) > 0:
            try:
                row = _state._get_or_create_user_state(self, s, cycle_uid)
                row.dismissed_date = None
                row.updated_at = datetime.now(timezone.utc)
                s.add(row)
                s.commit()
            except Exception:
                logger.exception("Failed to reset dismissed date for user=%s", cycle_uid)
            if _state._scope(user_id) == DEFAULT_SCOPE:
                self._dismissed_date = None

        return summary

    try:
        if session:
            return _do_cycle(session)
        with Session(_facade_engine()) as s:
            return _do_cycle(s)
    finally:
        self._is_inspecting = False


async def _scheduler_loop(self):
    """Background asynchronous periodic inspection loop."""
    while True:
        try:
            await asyncio.sleep(60)  # Check every 60 seconds
            if not self.settings.enabled:
                continue

            now = datetime.now(timezone.utc)
            should_run = False

            # 1. Interval-based trigger
            if self._last_run_time:
                if (now - self._last_run_time) >= timedelta(hours=self.settings.interval_hours):
                    should_run = True
            else:
                should_run = True

            # 2. Daily briefing target time check (UTC or system local time)
            current_utc_str = now.strftime("%H:%M")
            try:
                current_local_str = datetime.now().astimezone().strftime("%H:%M")
            except Exception:
                current_local_str = current_utc_str

            if (
                current_utc_str == self.settings.daily_briefing_time
                or current_local_str == self.settings.daily_briefing_time
            ):
                # Prevent multiple runs within the same 2-minute window
                if not self._last_run_time or (now - self._last_run_time).total_seconds() >= 120:
                    should_run = True

            if should_run:
                # Run in threadpool to avoid blocking async event loop
                await asyncio.to_thread(self.run_inspection_cycle)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Inspection scheduler loop iteration failed: %s", exc)
            await asyncio.sleep(10)


async def start(self):
    """Starts the background scheduler loop."""
    if self._loop_task is None or self._loop_task.done():
        self._loop_task = asyncio.create_task(_scheduler_loop(self, ))


async def stop(self):
    """Gracefully terminates the background scheduler loop."""
    if self._loop_task and not self._loop_task.done():
        self._loop_task.cancel()
        try:
            await self._loop_task
        except asyncio.CancelledError:
            pass
        self._loop_task = None
