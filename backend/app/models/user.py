import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Dict, TYPE_CHECKING

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .draft import Draft
    from .dna_record import DNARecord
    from .material import Material
    from .feedback import DraftFeedback


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default=None, index=True, unique=True)

    # Flexible and schema-less storage of user profiles and Cognitive Memory
    profile_data: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    drafts: list["Draft"] = Relationship(back_populates="user")
    dna_records: list["DNARecord"] = Relationship(back_populates="user")
    materials: list["Material"] = Relationship(back_populates="user")
    feedbacks: list["DraftFeedback"] = Relationship(back_populates="user")
