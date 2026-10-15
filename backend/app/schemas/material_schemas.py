from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class MaterialCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500, description="Title or headline of the material.")
    cleaned_content: Optional[str] = Field(default="", description="Clean main text body.")
    raw_content: Optional[str] = Field(default=None, description="Original raw HTML or text.")
    material_type: str = Field(default="personal", description="'trending', 'benchmark', or 'personal'")
    source_platform: Optional[str] = Field(default="manual", description="'wechat', 'xiaohongshu', 'weibo', 'zhihu', 'web', 'manual'")
    source_url: Optional[str] = Field(default=None, description="Source web link.")
    source_author: Optional[str] = Field(default=None, description="Original author or creator.")
    blueprint_data: Optional[Dict[str, Any]] = Field(default=None, description="Extracted structural bones.")
    tags: Optional[List[str]] = Field(default_factory=list, description="Categorical or semantic tags.")
    status: str = Field(default="inbox", description="'inbox', 'archived', 'used', 'discarded'")
    meta_info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Engagement, hot values, or platform stats.")
    user_id: Optional[str] = Field(default=None, description="Optional owner user ID.")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Material title cannot be empty.")
        return v.strip()


class MaterialUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, description="Updated title.")
    cleaned_content: Optional[str] = Field(default=None, description="Updated text content.")
    status: Optional[str] = Field(default=None, description="'inbox', 'archived', 'used', 'discarded'")
    tags: Optional[List[str]] = Field(default=None, description="Updated tags.")
    blueprint_data: Optional[Dict[str, Any]] = Field(default=None, description="Updated blueprint data.")
    meta_info: Optional[Dict[str, Any]] = Field(default=None, description="Updated meta info.")


class CollectUrlRequest(BaseModel):
    url: str = Field(min_length=1, description="Web URL to fetch and parse.")
    extract_blueprint: bool = Field(default=True, description="Whether to extract structural bones.")
    user_id: Optional[str] = Field(default=None, description="Optional user ID.")
    tags: Optional[List[str]] = Field(default=None, description="Optional extra tags.")
    title: Optional[str] = Field(default=None, description="Optional title override.")
    save: bool = Field(default=True, description="Whether to immediately persist into materials library.")


class FetchTrendingRequest(BaseModel):
    platform: Optional[str] = Field(default="all", description="'all', 'weibo', 'zhihu', 'xiaohongshu', 'wechat'")
    limit: int = Field(default=10, ge=1, le=50, description="Max number of hot topics to return.")
    batch_save: bool = Field(default=True, description="Whether to batch save trending items as materials.")
    user_id: Optional[str] = Field(default=None, description="Optional user ID.")


class MaterialResponse(BaseModel):
    id: str
    user_id: str
    material_type: str
    source_platform: Optional[str] = None
    source_url: Optional[str] = None
    source_author: Optional[str] = None
    title: str
    raw_content: Optional[str] = None
    cleaned_content: str
    blueprint_data: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    status: str
    meta_info: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
