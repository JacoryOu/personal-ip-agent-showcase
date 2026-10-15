import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User


class BenchmarkAccount(SQLModel, table=True):
    __tablename__ = "benchmark_accounts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # Relationship
    user: Optional["User"] = Relationship()

    # 'wechat', 'xhs', 'zhihu'
    platform: str = Field(index=True)
    account_name: str = Field(index=True)
    account_id: str = Field(index=True)  # Platform user id / fakeid / url_token
    home_url: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    bio: Optional[str] = Field(default=None)

    follower_count: Optional[int] = Field(default=0)
    notes_count: Optional[int] = Field(default=0)
    last_synced_at: Optional[datetime] = Field(default=None)

    # 'active', 'paused'
    status: str = Field(default="active", index=True)

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
