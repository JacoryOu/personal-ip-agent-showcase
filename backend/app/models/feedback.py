# -*- coding: utf-8 -*-
"""Data model for audience feedback and cognitive evolution."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User
    from .draft import Draft


class DraftFeedback(SQLModel, table=True):
    __tablename__ = "draft_feedbacks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    draft_id: uuid.UUID = Field(foreign_key="drafts.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="feedbacks")
    draft: Optional["Draft"] = Relationship(back_populates="feedbacks")

    # Raw reader comments or review text pasted by user
    comments_text: str = Field(default="")

    # Engagement metrics (likes, reads, collects, shares, comments_count, controversy_rate)
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    # Extracted insights by LLM: resonant_ideas, controversy_points, inspiration_notes
    extracted_insights: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    # Historical record of which ThinkingDNA traits received confidence boost
    boosted_dna_traits: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    # IDs of auto-saved personal notes in MaterialVault
    saved_material_ids: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
