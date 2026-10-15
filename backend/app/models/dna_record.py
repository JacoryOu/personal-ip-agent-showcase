import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User


class DNARecord(SQLModel, table=True):
    __tablename__ = "dna_records"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    draft_id: Optional[uuid.UUID] = Field(default=None, foreign_key="drafts.id", index=True)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="dna_records")

    # Thinking DNA extraction (vocabulary, logic preferences, values)
    dna_data: Any = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
