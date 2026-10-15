from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.db import get_session
from app.schemas.scheduler_schemas import (
    DailyBriefingResponse,
    InspectionQuotaUpdateRequest,
    SchedulerSettings,
    SchedulerSettingsUpdateRequest,
    SchedulerStatusResponse,
    SchedulerTriggerResponse,
)
from app.services.inspection_scheduler_service import inspection_scheduler

router = APIRouter(tags=["scheduler"])


def _resolve_acting_user_id(current_user: AuthenticatedUser) -> str:
    """Resolve the identity the scheduler is allowed to act on.

    The acting identity now comes from the authenticated credential only.
    A caller-supplied ``user_id`` (query or body) is never trusted and is
    ignored by every scheduler route, so one API-key holder cannot consume,
    mutate or inspect another user's inspection quota and settings.
    """
    return str(current_user.id)


@router.get("/quota", response_model=Dict[str, Any])
def get_inspection_quota(
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns the current external-call quota / pre-authorization state."""
    return inspection_scheduler.get_quota_status(
        session=session, user_id=_resolve_acting_user_id(current_user)
    )


@router.put("/quota", response_model=Dict[str, Any])
def update_inspection_quota(
    payload: InspectionQuotaUpdateRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Grants or revokes pre-authorization and adjusts unattended call limits."""
    return inspection_scheduler.set_quota_grant(
        session=session,
        user_id=_resolve_acting_user_id(current_user),
        authorized=payload.authorized,
        enabled=payload.enabled,
        daily_limit=payload.daily_limit,
        per_run_limit=payload.per_run_limit,
    )


@router.get("/status", response_model=SchedulerStatusResponse)
def get_scheduler_status(
    user_id: Optional[str] = Query(default=None, deprecated=True),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns the current status of the background inspection scheduler, last run summary, and unread briefing count."""
    return inspection_scheduler.get_status(
        session=session, user_id=_resolve_acting_user_id(current_user)
    )


@router.post("/trigger", response_model=SchedulerTriggerResponse)
def trigger_inspection(
    user_id: Optional[str] = Query(default=None, deprecated=True),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Immediately triggers a manual dual-wheel inspection cycle (trending topics harvest + benchmark viral deconstruct)."""
    res = inspection_scheduler.run_inspection_cycle(
        session=session, user_id=_resolve_acting_user_id(current_user)
    )
    return {**res, "summary": res}


@router.post("/settings", response_model=SchedulerSettings)
def update_scheduler_settings(
    payload: SchedulerSettingsUpdateRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SchedulerSettings:
    """Updates inspection interval, daily briefing target time, interest tags, and automated toggles.

    Settings are stored per authenticated user; there is no process-wide
    scheduler configuration any more (the background loop keeps its own
    private default scope).
    """
    return inspection_scheduler.update_settings(
        payload.model_dump(exclude_unset=True),
        user_id=_resolve_acting_user_id(current_user),
        session=session,
    )


@router.get("/briefing/today", response_model=DailyBriefingResponse)
def get_today_briefing(
    user_id: Optional[str] = Query(default=None, deprecated=True),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieves today's aggregated briefing containing hot viral topics and benchmark structural blueprints."""
    return inspection_scheduler.get_today_briefing(
        session=session, user_id=_resolve_acting_user_id(current_user)
    )


@router.post("/briefing/mark-read", response_model=Dict[str, Any])
def mark_briefing_as_read(
    date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format to mark as read"),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Marks today's or specified date's briefing as read/dismissed for the caller."""
    return inspection_scheduler.mark_briefing_read(
        date_str=date,
        user_id=_resolve_acting_user_id(current_user),
        session=session,
    )


@router.post("/briefing/confirm", response_model=Dict[str, Any])
def confirm_briefing_vault(
    user_id: Optional[str] = Query(default=None, deprecated=True),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Confirms all briefing items into the vault and marks today's briefing as read."""
    return inspection_scheduler.confirm_briefing_into_vault(
        session=session, user_id=_resolve_acting_user_id(current_user)
    )
