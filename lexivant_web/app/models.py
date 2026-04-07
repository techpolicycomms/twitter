"""SQLAlchemy ORM models for RegWatch."""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImpactLevel(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ReportType(str, enum.Enum):
    DAILY_DIGEST = "daily_digest"
    WEEKLY_LINKEDIN = "weekly_linkedin"
    MONTHLY_NEWSLETTER = "monthly_newsletter"


class AlertStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class RegulationItem(Base):
    """A scraped regulatory document or announcement."""

    __tablename__ = "regulation_items"
    __table_args__ = (UniqueConstraint("url_hash", name="uq_regulation_url_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    raw_content: Mapped[str] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Claude analysis fields
    analyzed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_relevant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    impact_level: Mapped[ImpactLevel | None] = mapped_column(
        Enum(ImpactLevel), nullable=True, index=True
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array as string
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Content-hash deduplication: SHA-256[:16] of raw_content — prevents re-analyzing
    # identical static gov pages scraped on consecutive days (zero additional Claude calls)
    content_hash: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)

    # Alert tracking
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alert_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="regulation_item")

    def __repr__(self) -> str:
        return f"<RegulationItem id={self.id} region={self.region} impact={self.impact_level}>"


class Alert(Base):
    """Tracks Slack/email alerts sent for HIGH impact items."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    regulation_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("regulation_items.id"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)  # "slack" or "email"
    recipient: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus), default=AlertStatus.PENDING, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    regulation_item: Mapped["RegulationItem"] = relationship(
        "RegulationItem", back_populates="alerts"
    )


class Report(Base):
    """Generated reports (digest, LinkedIn post, newsletter)."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # plain text / markdown
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)  # HTML for email
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<Report id={self.id} type={self.report_type} sent={self.sent}>"


class ScrapeRun(Base):
    """Audit log of scrape runs per source."""

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
