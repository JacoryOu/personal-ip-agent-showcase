import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User
    from .material import Material
    from .feedback import DraftFeedback


class Draft(SQLModel, table=True):
    __tablename__ = "drafts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="drafts")
    source_material: Optional["Material"] = Relationship(back_populates="drafts")
    feedbacks: list["DraftFeedback"] = Relationship(
        back_populates="draft",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    topic: str
    original_ai_draft: str
    user_final_draft: Optional[str] = Field(default=None)

    # Lineage tracking
    source_material_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="materials.id", index=True
    )
    benchmark_blueprint_id: Optional[str] = Field(default=None)
    lineage_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    # For storing A/B divergent outlines, chosen outline, metadata
    metadata_: Any = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON().with_variant(JSONB, "postgresql")),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
