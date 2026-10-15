import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User
    from .draft import Draft


class Material(SQLModel, table=True):
    __tablename__ = "materials"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="materials")
    drafts: list["Draft"] = Relationship(back_populates="source_material")

    # 'trending', 'benchmark', 'personal'
    material_type: str = Field(default="benchmark", index=True)

    # 'wechat', 'xiaohongshu', 'weibo', 'zhihu', 'web', 'manual'
    source_platform: Optional[str] = Field(default=None, index=True)
    source_url: Optional[str] = Field(default=None)
    source_author: Optional[str] = Field(default=None)

    title: str = Field(default="")
    raw_content: Optional[str] = Field(default=None)
    cleaned_content: str = Field(default="")

    # JSON/JSONB for extracted structural bones
    blueprint_data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    # JSON/JSONB for tags
    tags: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    # 'inbox', 'archived', 'used', 'discarded'
    status: str = Field(default="inbox", index=True)

    # JSON/JSONB for hot value, engagement, metrics, etc.
    meta_info: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
