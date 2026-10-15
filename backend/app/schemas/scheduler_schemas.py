from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SchedulerSettings(BaseModel):
    enabled: bool = Field(default=True, description="Whether background inspection is enabled")
    interval_hours: int = Field(default=6, ge=1, le=48, description="Inspection interval in hours")
    daily_briefing_time: str = Field(default="08:30", description="Daily scheduled briefing time in HH:MM format")
    wheel1_enabled: bool = Field(default=True, description="Wheel 1: Trending radar inspection enabled")
    wheel2_enabled: bool = Field(default=True, description="Wheel 2: Benchmark accounts silent deconstruct enabled")
    interest_tags: List[str] = Field(
        default_factory=lambda: ["AI", "商业", "独立开发", "超级个体", "效率", "技术变现"],
        description="User interest tags used for filtering trending radar topics",
    )
    viral_threshold_likes: int = Field(
        default=3000,
        ge=0,
        description="Minimum likes threshold to consider a post viral for automatic blueprint deconstruction",
    )
    max_trending_per_run: int = Field(default=10, ge=1, le=50, description="Max trending topics to harvest per run")
    max_posts_per_account: int = Field(default=5, ge=1, le=20, description="Max posts to inspect per benchmark account")
    notify_unread: bool = Field(default=True, description="Whether to show notification pill for unread briefing")


class SchedulerSettingsUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_hours: Optional[int] = Field(default=None, ge=1, le=48)
    daily_briefing_time: Optional[str] = None
    wheel1_enabled: Optional[bool] = None
    wheel2_enabled: Optional[bool] = None
    interest_tags: Optional[List[str]] = None
    viral_threshold_likes: Optional[int] = Field(default=None, ge=0)
    max_trending_per_run: Optional[int] = Field(default=None, ge=1, le=50)
    max_posts_per_account: Optional[int] = Field(default=None, ge=1, le=20)
    notify_unread: Optional[bool] = None


class LastExecutionSummary(BaseModel):
    success: bool = True
    wheel1_new_topics: int = 0
    wheel2_new_blueprints: int = 0
    total_new_items: int = 0
    duration_ms: int = 0
    message: str = ""
    executed_at: Optional[str] = None


class SchedulerStatusResponse(BaseModel):
    running: bool
    enabled: bool
    interval_hours: int
    daily_briefing_time: str
    next_run_time: Optional[str] = None
    last_run_time: Optional[str] = None
    last_execution_summary: Optional[Dict[str, Any]] = None
    settings: SchedulerSettings
    unread_briefing_count: int = 0
    inspection_quota: Dict[str, Any] = Field(default_factory=dict)
    last_quota_decision: Optional[Dict[str, Any]] = None


class SchedulerTriggerResponse(BaseModel):
    success: bool
    message: str
    wheel1_new_topics: int
    wheel2_new_blueprints: int
    total_new_items: int
    duration_ms: int
    executed_at: Optional[str] = None
    denied_reason: Optional[str] = None
    summary: Optional[Dict[str, Any]] = Field(default_factory=dict)


class InspectionQuotaUpdateRequest(BaseModel):
    """Pre-authorization / quota grant for unattended inspection external calls."""

    authorized: bool
    enabled: Optional[bool] = None
    daily_limit: Optional[int] = Field(default=None, ge=0, le=1000)
    per_run_limit: Optional[int] = Field(default=None, ge=0, le=100)


class DailyBriefingResponse(BaseModel):
    date: str
    generated_at: str
    unread: bool
    total_items: int
    trending_count: int
    benchmark_count: int
    trending_topics: List[Dict[str, Any]]
    benchmark_blueprints: List[Dict[str, Any]]
