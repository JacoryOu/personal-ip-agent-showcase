import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CredentialResponse(BaseModel):
    id: str
    user_id: str
    platform: str
    account_identifier: Optional[str] = None
    status: str
    has_cookies: bool = False
    cookie_keys: List[str] = Field(default_factory=list)
    last_checked_at: Optional[str] = None
    expires_at: Optional[str] = None
    meta_info: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class QRLoginStartRequest(BaseModel):
    platform: str = Field(..., description="'wechat', 'xhs', or 'zhihu'")
    user_id: Optional[str] = None


class QRLoginStartResponse(BaseModel):
    session_key: str
    platform: str
    qr_code_data: str
    expires_in: int = 180
    instructions: str


class QRLoginStatusResponse(BaseModel):
    session_key: str
    platform: str
    status: str  # 'pending', 'scanned', 'confirmed', 'expired'
    message: str
    credential: Optional[CredentialResponse] = None


class QRLoginSimulateConfirmRequest(BaseModel):
    session_key: str
    account_identifier: Optional[str] = None


class ManualCookieRequest(BaseModel):
    platform: str = Field(..., description="'wechat', 'xhs', or 'zhihu'")
    cookies: Any = Field(..., description="Cookie dict or string")
    account_identifier: Optional[str] = None
    user_id: Optional[str] = None


class BenchmarkAccountCreateRequest(BaseModel):
    platform: str = Field(..., description="'wechat', 'xhs', or 'zhihu'")
    account_name: str
    account_id: Optional[str] = None
    home_url: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    user_id: Optional[str] = None


class BenchmarkAccountUpdateRequest(BaseModel):
    account_name: Optional[str] = None
    home_url: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    status: Optional[str] = None


class BenchmarkAccountResponse(BaseModel):
    id: str
    user_id: str
    platform: str
    account_name: str
    account_id: str
    home_url: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    follower_count: int = 0
    notes_count: int = 0
    last_synced_at: Optional[str] = None
    status: str = "active"
    meta_info: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FeedItem(BaseModel):
    id: str
    title: str
    url: str
    author: str
    platform: str
    content: str
    summary: str
    cover_url: Optional[str] = None
    publish_time: str
    likes: int = 0
    collects: int = 0
    comments: int = 0
    shares: int = 0
    hot_score: int = 0
    tags: List[str] = Field(default_factory=list)
    is_ingested: bool = False


class AccountFeedResponse(BaseModel):
    account: BenchmarkAccountResponse
    items: List[FeedItem]
    sort_by: str = "latest"  # 'latest' or 'hot'
    total: int = 0
    has_active_credential: bool = False


class BatchIngestRequest(BaseModel):
    user_id: Optional[str] = None
    items: List[FeedItem]
    extract_blueprint: bool = True
    category: Optional[str] = "benchmark"
    tags: Optional[List[str]] = None


class BatchIngestResponse(BaseModel):
    success: bool
    count: int
    material_ids: List[str] = Field(default_factory=list)
    materials: List[Dict[str, Any]] = Field(default_factory=list)
