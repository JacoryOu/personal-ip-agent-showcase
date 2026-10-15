# -*- coding: utf-8 -*-
"""Quota / pre-authorization guard for unattended inspection external calls.

Design goals:
- Unattended runs must never depend on an interactive approval prompt, so the
  decision is made entirely from persisted, user-scoped state.
- Fail closed: unknown user, missing grant, or exhausted budget => deny + record.
- Every decision is recorded (granted or denied) so it is observable.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlmodel import Session, select

from app.models.inspection_quota import InspectionQuota

logger = logging.getLogger(__name__)

DEFAULT_DAILY_LIMIT = 5
DEFAULT_PER_RUN_LIMIT = 1


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_quota(session: Session, user_id: uuid.UUID) -> InspectionQuota:
    q = session.exec(
        select(InspectionQuota).where(InspectionQuota.user_id == user_id)
    ).first()
    if q is None:
        q = InspectionQuota(
            id=uuid.uuid4(),
            user_id=user_id,
            enabled=True,
            authorized=False,
            daily_limit=DEFAULT_DAILY_LIMIT,
            per_run_limit=DEFAULT_PER_RUN_LIMIT,
            day=_utc_day(),
            used_today=0,
            used_this_run=0,
        )
        session.add(q)
        session.commit()
        session.refresh(q)
    return q


def _roll_day(q: InspectionQuota) -> None:
    today = _utc_day()
    if q.day != today:
        q.day = today
        q.used_today = 0


def reset_run(q: InspectionQuota) -> None:
    _roll_day(q)
    q.used_this_run = 0
    q.last_error = None


def check_and_consume(
    session: Session,
    user_id: uuid.UUID,
    *,
    runs: int = 1,
) -> Dict[str, Any]:
    """Try to consume ``runs`` external-call budget for ``user_id``.

    Returns a decision dict: ``{"allowed": bool, "reason": str, ...}``.
    Always records the outcome. Never raises for policy denial.
    """
    now = datetime.now(timezone.utc)
    q = get_quota(session, user_id)
    _roll_day(q)

    def _deny(reason: str) -> Dict[str, Any]:
        q.last_denied_at = now
        q.last_denial_reason = reason
        q.total_denied += 1
        session.add(q)
        session.commit()
        logger.warning(
            "Inspection external call DENIED user=%s reason=%s", user_id, reason
        )
        return {
            "allowed": False,
            "reason": reason,
            "user_id": str(user_id),
            "daily_limit": q.daily_limit,
            "per_run_limit": q.per_run_limit,
            "used_today": q.used_today,
        }

    if not q.enabled:
        return _deny("scheduler_disabled")
    if not q.authorized:
        return _deny("not_pre_authorized")
    if runs > q.per_run_limit:
        return _deny("per_run_limit_exceeded")
    if q.used_this_run + runs > q.per_run_limit:
        return _deny("per_run_limit_exceeded")
    if q.used_today + runs > q.daily_limit:
        return _deny("daily_limit_exceeded")

    q.used_today += runs
    q.used_this_run += runs
    q.total_runs += runs
    q.last_run_at = now
    q.last_denial_reason = None
    session.add(q)
    session.commit()
    logger.info("Inspection external call GRANTED user=%s runs=%s", user_id, runs)
    return {
        "allowed": True,
        "reason": "granted",
        "user_id": str(user_id),
        "daily_limit": q.daily_limit,
        "per_run_limit": q.per_run_limit,
        "used_today": q.used_today,
    }


def record_error(session: Session, user_id: uuid.UUID, message: str) -> None:
    q = get_quota(session, user_id)
    q.last_error = message[:2000]
    session.add(q)
    session.commit()
    logger.error("Inspection run error user=%s: %s", user_id, message)


def get_status(session: Session, user_id: uuid.UUID) -> Dict[str, Any]:
    q = get_quota(session, user_id)
    _roll_day(q)
    session.add(q)
    session.commit()
    return {
        "user_id": str(user_id),
        "enabled": q.enabled,
        "authorized": q.authorized,
        "daily_limit": q.daily_limit,
        "per_run_limit": q.per_run_limit,
        "day": q.day,
        "used_today": q.used_today,
        "remaining_today": max(0, q.daily_limit - q.used_today),
        "used_this_run": q.used_this_run,
        "total_runs": q.total_runs,
        "total_denied": q.total_denied,
        "last_run_at": q.last_run_at.isoformat() if q.last_run_at else None,
        "last_denied_at": q.last_denied_at.isoformat() if q.last_denied_at else None,
        "last_denial_reason": q.last_denial_reason,
        "last_error": q.last_error,
    }


def set_grant(
    session: Session,
    user_id: uuid.UUID,
    *,
    authorized: bool,
    enabled: Optional[bool] = None,
    daily_limit: Optional[int] = None,
    per_run_limit: Optional[int] = None,
) -> Dict[str, Any]:
    q = get_quota(session, user_id)
    q.authorized = authorized
    if enabled is not None:
        q.enabled = enabled
    if daily_limit is not None:
        q.daily_limit = max(0, daily_limit)
    if per_run_limit is not None:
        q.per_run_limit = max(0, per_run_limit)
    q.used_this_run = 0
    q.updated_at = datetime.now(timezone.utc)
    session.add(q)
    session.commit()
    logger.info(
        "Inspection quota updated user=%s authorized=%s enabled=%s",
        user_id,
        authorized,
        q.enabled,
    )
    return get_status(session, user_id)
