# -*- coding: utf-8 -*-
"""Persisted per-user state for the unattended inspection scheduler.

Why this table exists
---------------------
``InspectionSchedulerService`` keeps four pieces of per-user state:
settings, the dismissed (read/confirmed) briefing date, the last quota
decision, and the last execution summary. Historically all four lived in
process-level dictionaries, which meant state was lost on restart and could
diverge between workers in a multi-process deployment.

This table persists exactly that state, keyed one row per user. It is a NEW
table only - no existing table's columns are modified - so
``SQLModel.metadata.create_all`` creates it without colliding with the other
security lines' schema work.

Scope note (deliberate, matches the service implementation)
----------------------------------------------------------
Rows exist only for *real* users. The background scheduler loop has no acting
user and keeps using the process-level ``DEFAULT_SCOPE`` configuration; that
entry deliberately stays in memory and is never written here, because there is
no ``users`` row to attach it to.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel


class SchedulerUserState(SQLModel, table=True):
    """Durable per-user scheduler state, scoped to exactly one user."""

    __tablename__ = "scheduler_user_states"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # One row per user; the scheduler never reads or writes another user's row.
    user_id: uuid.UUID = Field(index=True, unique=True)

    # Serialized SchedulerSettings (model_dump() of app.schemas.scheduler_schemas).
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    # YYYY-MM-DD of the last briefing the user read / confirmed.
    dismissed_date: Optional[str] = Field(default=None)

    # Last quota decision payload returned by the quota gate, and the last
    # execution summary surfaced on the status endpoint.
    quota_decision: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )
    last_summary: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
