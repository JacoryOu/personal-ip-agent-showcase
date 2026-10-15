"""EpisodicStory model – records personal stories for cognitive memory."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel


class EpisodicStory(SQLModel, table=True):
    __tablename__ = "episodic_stories"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(index=True)

    title: str = Field(default="")
    story_content: str = Field(default="")
    story_type: str = Field(
        default="daily_life",
        description="One of: daily_life | failure_reflection | client_case",
    )

    occurred_at: Optional[datetime] = Field(
        default=None,
        index=True,
    )

    # JSON list of string tags
    tags: Any = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )

    confidence_score: float = Field(default=1.0)

    # numpy float32 array serialized to bytes (Plan B embedding)
    embedding: Optional[bytes] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
