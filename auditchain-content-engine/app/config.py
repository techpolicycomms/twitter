"""
Application configuration via pydantic-settings.
All values are loaded from environment variables or .env file.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Anthropic ─────────────────────────────────────────────
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    # ── Database ──────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://auditchain:secret@localhost:5432/content_engine"
    )
    sync_database_url: str = Field(
        default="postgresql+psycopg2://auditchain:secret@localhost:5432/content_engine"
    )

    # ── App ───────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # ── Buffer ────────────────────────────────────────────────
    buffer_access_token: str = ""
    buffer_profile_ids_linkedin: str = ""
    buffer_profile_ids_twitter: str = ""

    # ── Optimal posting times (UTC hours) ─────────────────────
    linkedin_optimal_hours: str = "9,12,17"
    twitter_optimal_hours: str = "8,12,16,20"
    blog_publish_hour: int = 10

    # ── Scheduler ─────────────────────────────────────────────
    scheduler_timezone: str = "UTC"
    news_scan_hour: int = 6
    content_gen_hour: int = 7

    # ── Content ───────────────────────────────────────────────
    max_news_items_per_feed: int = 20
    rapid_response_threshold: float = 0.8

    # ── RSS Feeds ─────────────────────────────────────────────
    rss_feeds: dict = {
        "MIT Technology Review": "https://www.technologyreview.com/feed/",
        "TechCabal": "https://techcabal.com/feed/",
        "Inc42": "https://inc42.com/feed/",
        "OECD AI Policy": "https://oecd.ai/en/wonk/feed",
        "EU AI Act Watch": "https://artificialintelligenceact.eu/feed/",
    }

    @property
    def linkedin_hours_list(self) -> List[int]:
        return [int(h) for h in self.linkedin_optimal_hours.split(",")]

    @property
    def twitter_hours_list(self) -> List[int]:
        return [int(h) for h in self.twitter_optimal_hours.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
