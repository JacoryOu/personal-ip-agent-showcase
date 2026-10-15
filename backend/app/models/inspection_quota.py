# -*- coding: utf-8 -*-
"""Per-user external-call budget and pre-authorization state for the unattended
inspection scheduler.

This is a NEW table only. No existing table's columns are modified, so
``SQLModel.metadata.create_all`` creates it without any migration conflict with
other security lines.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel


class InspectionQuota(SQLModel, table=True):
    """Unattended-inspection budget + grant state, scoped to one user."""

    __tablename__ = "inspection_quotas"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # The scheduler only ever acts on behalf of this user. The API layer refuses
    # to act on a user_id that is not the caller's own resolved identity.
    user_id: uuid.UUID = Field(index=True, unique=True)

    # Master switch for unattended (scheduler-driven) external calls.
    enabled: bool = Field(default=True)

    # Explicit pre-authorization: unattended runs are allowed only when granted.
    authorized: bool = Field(default=False)

    daily_limit: int = Field(default=5, ge=0)
    per_run_limit: int = Field(default=1, ge=0)

    # Counters for the current UTC day / current run.
    day: str = Field(default="")
    used_today: int = Field(default=0, ge=0)
    used_this_run: int = Field(default=0, ge=0)

    # Observability.
    last_run_at: Optional[datetime] = Field(default=None)
    last_denied_at: Optional[datetime] = Field(default=None)
    last_denial_reason: Optional[str] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
    total_runs: int = Field(default=0, ge=0)
    total_denied: int = Field(default=0, ge=0)

    extra_data: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
