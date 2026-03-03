"""
Pydantic schemas for request/response validation and serialization.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import ContentPillar, ContentStatus, Platform


# ── Calendar ───────────────────────────────────────────────────────────────


class CalendarEntryBase(BaseModel):
    entry_date: date
    topic: str
    platform: Platform
    content_pillar: ContentPillar


class CalendarEntryOut(CalendarEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_generated: bool
    created_at: datetime


# ── Generated Content ──────────────────────────────────────────────────────


class GeneratedContentBase(BaseModel):
    platform: Platform
    content_pillar: ContentPillar
    topic: str
    body: str
    hashtags: Optional[str] = None
    word_count: Optional[int] = None
    tweet_count: Optional[int] = None
    source_type: str = "calendar"


class GeneratedContentOut(GeneratedContentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ContentStatus
    reviewer_notes: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    published_at: Optional[datetime] = None
    buffer_update_id: Optional[str] = None
    model_used: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    calendar_entry_id: Optional[int] = None
    news_item_id: Optional[int] = None


class ContentUpdateRequest(BaseModel):
    status: Optional[ContentStatus] = None
    reviewer_notes: Optional[str] = None
    body: Optional[str] = None
    scheduled_for: Optional[datetime] = None


class ContentApproveRequest(BaseModel):
    reviewer_notes: Optional[str] = None
    scheduled_for: Optional[datetime] = None


# ── News Items ─────────────────────────────────────────────────────────────


class NewsItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feed_name: str
    title: str
    url: str
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    relevance_score: Optional[float] = None
    relevance_reason: Optional[str] = None
    suggested_angle: Optional[str] = None
    is_rapid_response: bool
    is_processed: bool
    fetched_at: datetime


# ── Engagement ─────────────────────────────────────────────────────────────


class EngagementMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: Platform
    metric_date: date
    impressions: Optional[int] = None
    engagements: Optional[int] = None
    likes: Optional[int] = None
    shares: Optional[int] = None
    comments: Optional[int] = None
    clicks: Optional[int] = None
    recorded_at: datetime


# ── Dashboard aggregates ───────────────────────────────────────────────────


class DashboardStats(BaseModel):
    total_drafts: int
    pending_review: int
    approved: int
    scheduled: int
    published: int
    rejected: int
    news_items_today: int
    rapid_responses_pending: int


class BufferExportItem(BaseModel):
    """Buffer API-compatible payload for a single post."""

    profile_ids: List[str]
    text: str
    scheduled_at: Optional[str] = None  # ISO 8601
    now: bool = False
    top: bool = False
    media: Optional[dict] = None
    shorten: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "profile_ids": ["abc123"],
                "text": "Thread: Understanding equalized odds...",
                "scheduled_at": "2026-03-04T09:00:00Z",
                "shorten": True,
            }
        }


class GenerateRequest(BaseModel):
    """Manual content generation trigger request."""

    topic: str = Field(..., min_length=5, max_length=500)
    platform: Platform
    content_pillar: ContentPillar
    additional_context: Optional[str] = None
