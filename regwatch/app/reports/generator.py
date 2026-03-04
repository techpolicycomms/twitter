"""Claude-powered report generator for daily digest, weekly LinkedIn, monthly newsletter."""
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from anthropic import AsyncAnthropic
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ImpactLevel, RegulationItem, Report, ReportType

logger = logging.getLogger(__name__)

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "reports"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _get_items_for_period(
    items: list[RegulationItem],
    min_impact: ImpactLevel | None = None,
    relevant_only: bool = True,
) -> list[RegulationItem]:
    """Filter items by impact level and relevance."""
    filtered = [i for i in items if not relevant_only or i.is_relevant]
    if min_impact == ImpactLevel.HIGH:
        filtered = [i for i in filtered if i.impact_level == ImpactLevel.HIGH]
    elif min_impact == ImpactLevel.MEDIUM:
        filtered = [
            i for i in filtered if i.impact_level in (ImpactLevel.HIGH, ImpactLevel.MEDIUM)
        ]
    return filtered


def _render_action_items(item: RegulationItem) -> list[str]:
    try:
        return json.loads(item.action_items or "[]")
    except json.JSONDecodeError:
        return []


# ---------------------------------------------------------------------------
# Daily Digest
# ---------------------------------------------------------------------------


async def generate_daily_digest(db: AsyncSession) -> Report | None:
    """Generate daily email digest for the past 24 hours."""
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(hours=24)

    result = await db.execute(
        select(RegulationItem)
        .where(
            and_(
                RegulationItem.analyzed == True,  # noqa: E712
                RegulationItem.scraped_at >= period_start,
            )
        )
        .order_by(RegulationItem.impact_level.desc(), RegulationItem.relevance_score.desc())
    )
    all_items = result.scalars().all()

    relevant_items = _get_items_for_period(all_items, relevant_only=True)

    if not relevant_items:
        logger.info("No relevant items for daily digest — skipping")
        return None

    # Separate by impact
    high_items = [i for i in relevant_items if i.impact_level == ImpactLevel.HIGH]
    medium_items = [i for i in relevant_items if i.impact_level == ImpactLevel.MEDIUM]
    low_items = [i for i in relevant_items if i.impact_level == ImpactLevel.LOW]

    # Group by region for the template
    regions: dict[str, list[RegulationItem]] = {}
    for item in relevant_items:
        regions.setdefault(item.region, []).append(item)

    template = _jinja_env.get_template("daily_digest.html")
    html_content = template.render(
        title=f"RegWatch Daily Digest — {now.strftime('%B %d, %Y')}",
        period=now.strftime("%B %d, %Y"),
        high_items=high_items,
        medium_items=medium_items,
        low_items=low_items,
        regions=regions,
        total_count=len(relevant_items),
        render_action_items=_render_action_items,
    )

    report = Report(
        report_type=ReportType.DAILY_DIGEST,
        title=f"RegWatch Daily Digest — {now.strftime('%B %d, %Y')}",
        content_html=html_content,
        period_start=period_start,
        period_end=now,
        item_count=len(relevant_items),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    logger.info("Daily digest generated: %d items", len(relevant_items))
    return report


# ---------------------------------------------------------------------------
# Weekly LinkedIn Post
# ---------------------------------------------------------------------------

LINKEDIN_SYSTEM = """You are the voice of AuditChain, an AI model auditing and
certification platform. Write authoritative, data-driven LinkedIn posts about
AI regulation developments. Tone: professional but accessible, forward-looking,
with a Global South perspective. Never use generic filler phrases."""

LINKEDIN_PROMPT = """Based on the following AI regulatory developments from the past week,
write a LinkedIn post for AuditChain that:
1. Opens with a compelling hook (1 sentence, no "I" statements)
2. Summarizes the 2-3 most important developments (concise, with country/region context)
3. Explains implications for AI auditing and algorithmic accountability
4. Closes with a forward-looking insight or call-to-action
5. Includes 5-7 relevant hashtags at the end

Keep it under 1200 characters (LinkedIn optimal length).

REGULATORY DEVELOPMENTS THIS WEEK:
{developments}

Return ONLY the LinkedIn post text, no preamble."""


async def generate_weekly_linkedin(db: AsyncSession) -> Report | None:
    """Generate weekly LinkedIn post summarizing key developments."""
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=7)

    result = await db.execute(
        select(RegulationItem)
        .where(
            and_(
                RegulationItem.analyzed == True,  # noqa: E712
                RegulationItem.is_relevant == True,  # noqa: E712
                RegulationItem.scraped_at >= period_start,
                RegulationItem.impact_level.in_([ImpactLevel.HIGH, ImpactLevel.MEDIUM]),
            )
        )
        .order_by(RegulationItem.impact_level.desc(), RegulationItem.relevance_score.desc())
        .limit(10)
    )
    top_items = result.scalars().all()

    if not top_items:
        logger.info("No relevant high/medium items for LinkedIn post — skipping")
        return None

    developments = "\n\n".join(
        f"[{item.region}] {item.title}\n"
        f"Source: {item.source_name}\n"
        f"Impact: {item.impact_level.value}\n"
        f"Summary: {item.ai_summary or 'N/A'}"
        for item in top_items
    )

    prompt = LINKEDIN_PROMPT.format(developments=developments)
    message = await _client.messages.create(
        model=settings.anthropic_model,
        max_tokens=600,
        system=LINKEDIN_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    post_text = message.content[0].text.strip()

    report = Report(
        report_type=ReportType.WEEKLY_LINKEDIN,
        title=f"RegWatch Weekly LinkedIn — {now.strftime('%B %d, %Y')}",
        content_text=post_text,
        period_start=period_start,
        period_end=now,
        item_count=len(top_items),
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    logger.info("Weekly LinkedIn post generated (%d chars)", len(post_text))
    return report


# ---------------------------------------------------------------------------
# Monthly Newsletter
# ---------------------------------------------------------------------------

NEWSLETTER_INTRO_PROMPT = """You are writing the introduction for AuditChain's monthly
RegWatch newsletter. This is sent to subscribers (compliance officers, AI ethics researchers,
policy makers, and tech leaders across Africa, India, and globally).

Write a 3-4 paragraph introduction (200-300 words) that:
1. Opens with the month's headline theme (what was the dominant regulatory story?)
2. Provides context on why these developments matter for AI auditing
3. Previews the key regions covered in this edition
4. Has a warm but professional tone — this is a trusted intelligence resource

Month: {month_year}
Key themes from this month:
{themes}

Key regions with activity: {regions}

Return only the introduction text, no headers."""


async def generate_monthly_newsletter(db: AsyncSession) -> Report | None:
    """Generate full monthly newsletter HTML."""
    now = datetime.now(timezone.utc)
    # Cover the previous full month
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = first_of_month
    period_start = (first_of_month - timedelta(days=1)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    result = await db.execute(
        select(RegulationItem)
        .where(
            and_(
                RegulationItem.analyzed == True,  # noqa: E712
                RegulationItem.is_relevant == True,  # noqa: E712
                RegulationItem.scraped_at >= period_start,
                RegulationItem.scraped_at < period_end,
            )
        )
        .order_by(RegulationItem.impact_level.desc(), RegulationItem.relevance_score.desc())
    )
    all_items = result.scalars().all()

    if not all_items:
        logger.info("No items for monthly newsletter — skipping")
        return None

    # Build themes string for Claude
    high_titles = [i.title for i in all_items if i.impact_level == ImpactLevel.HIGH][:5]
    themes_text = "\n".join(f"- {t}" for t in high_titles) or "General AI governance updates"
    active_regions = list({i.region for i in all_items})

    # Generate intro
    intro_prompt = NEWSLETTER_INTRO_PROMPT.format(
        month_year=period_start.strftime("%B %Y"),
        themes=themes_text,
        regions=", ".join(active_regions),
    )
    intro_msg = await _client.messages.create(
        model=settings.anthropic_model,
        max_tokens=500,
        messages=[{"role": "user", "content": intro_prompt}],
    )
    intro_text = intro_msg.content[0].text.strip()

    # Group by region
    by_region: dict[str, list[RegulationItem]] = {}
    for item in all_items:
        by_region.setdefault(item.region, []).append(item)

    high_items = [i for i in all_items if i.impact_level == ImpactLevel.HIGH]
    medium_items = [i for i in all_items if i.impact_level == ImpactLevel.MEDIUM]

    template = _jinja_env.get_template("monthly_newsletter.html")
    html_content = template.render(
        title=f"RegWatch Monthly Intelligence — {period_start.strftime('%B %Y')}",
        month_year=period_start.strftime("%B %Y"),
        intro_text=intro_text,
        high_items=high_items,
        medium_items=medium_items,
        by_region=by_region,
        total_count=len(all_items),
        render_action_items=_render_action_items,
        period_start=period_start,
        period_end=period_end,
    )

    report = Report(
        report_type=ReportType.MONTHLY_NEWSLETTER,
        title=f"RegWatch Monthly Intelligence — {period_start.strftime('%B %Y')}",
        content_html=html_content,
        period_start=period_start,
        period_end=period_end,
        item_count=len(all_items),
        input_tokens=intro_msg.usage.input_tokens,
        output_tokens=intro_msg.usage.output_tokens,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    logger.info("Monthly newsletter generated: %d items", len(all_items))
    return report
