import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User


class PlatformAccountCredential(SQLModel, table=True):
    __tablename__ = "platform_credentials"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # Relationship
    user: Optional["User"] = Relationship()

    # 'wechat', 'xhs', 'zhihu'
    platform: str = Field(index=True)
    account_identifier: Optional[str] = Field(default=None)  # Nickname, username or MP token name

    # Auth credentials / cookies (e.g. a1, web_session, token, slave_sid, z_c0)
    cookies: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql")),
    )

    # Status: 'active', 'expired', 'pending_login', 'invalid'
    status: str = Field(default="pending_login", index=True)

    # QR Code data URI or session key for polling login state
    qr_code_data: Optional[str] = Field(default=None)
    session_key: Optional[str] = Field(default=None, index=True)

    last_checked_at: Optional[datetime] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)

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
