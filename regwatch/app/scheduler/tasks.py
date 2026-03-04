"""APScheduler tasks for RegWatch: scrape, analyze, alert, report."""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import AsyncSessionLocal
from app.notifications.alert_manager import process_pending_alerts
from app.notifications.email import send_report_email
from app.reports.generator import (
    generate_daily_digest,
    generate_monthly_newsletter,
    generate_weekly_linkedin,
)
from app.scrapers import ALL_SCRAPERS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job functions
# ---------------------------------------------------------------------------


async def job_scrape_all() -> None:
    """Scrape all sources, analyze new items, send HIGH impact alerts."""
    logger.info("[scheduler] Starting scrape run at %s", datetime.now(timezone.utc).isoformat())
    async with AsyncSessionLocal() as db:
        total_new = 0
        for ScraperClass in ALL_SCRAPERS:
            try:
                scraper = ScraperClass()
                new_items = await scraper.scrape(db)
                total_new += len(new_items)
            except Exception as exc:
                logger.error("[scheduler] Scraper %s failed: %s", ScraperClass.source_key, exc)

        logger.info("[scheduler] Scrape complete. Total new items: %d", total_new)

    # Analyze in a fresh session
    if total_new > 0:
        from app.analysis.analyzer import analyze_all_pending

        async with AsyncSessionLocal() as db:
            analyzed = await analyze_all_pending(db)
            logger.info("[scheduler] Analysis complete: %d items", analyzed)

        # Send pending HIGH impact alerts
        async with AsyncSessionLocal() as db:
            alerts_sent = await process_pending_alerts(db)
            logger.info("[scheduler] Alerts sent: %d", alerts_sent)


async def job_daily_digest() -> None:
    """Generate and send the daily email digest."""
    logger.info("[scheduler] Generating daily digest")
    async with AsyncSessionLocal() as db:
        report = await generate_daily_digest(db)
        if report and settings.team_email_recipients:
            sent = await send_report_email(
                report,
                settings.team_email_recipients,
                subject=report.title,
            )
            if sent:
                from datetime import datetime, timezone

                report.sent = True
                report.sent_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info("[scheduler] Daily digest sent")


async def job_weekly_linkedin() -> None:
    """Generate weekly LinkedIn post (stored in DB for manual review/post)."""
    logger.info("[scheduler] Generating weekly LinkedIn post")
    async with AsyncSessionLocal() as db:
        report = await generate_weekly_linkedin(db)
        if report:
            logger.info(
                "[scheduler] LinkedIn post ready (report ID %d):\n%s",
                report.id,
                report.content_text[:200] if report.content_text else "",
            )


async def job_monthly_newsletter() -> None:
    """Generate and send the monthly newsletter to subscribers."""
    logger.info("[scheduler] Generating monthly newsletter")
    async with AsyncSessionLocal() as db:
        report = await generate_monthly_newsletter(db)
        if report:
            if settings.newsletter_list_id:
                from app.notifications.email import send_newsletter_via_sendgrid_list

                await send_newsletter_via_sendgrid_list(report, settings.newsletter_list_id)
            elif settings.team_email_recipients:
                await send_report_email(report, settings.team_email_recipients)
            report.sent = True
            report.sent_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("[scheduler] Monthly newsletter sent")


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Daily scrape + analysis + alerts (06:00 UTC)
    scheduler.add_job(
        job_scrape_all,
        CronTrigger(hour=settings.scrape_hour, minute=settings.scrape_minute),
        id="scrape_all",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Daily digest email (08:00 UTC)
    scheduler.add_job(
        job_daily_digest,
        CronTrigger(hour=settings.digest_hour, minute=settings.digest_minute),
        id="daily_digest",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Weekly LinkedIn post (every Monday at 09:00 UTC)
    scheduler.add_job(
        job_weekly_linkedin,
        CronTrigger(
            day_of_week=settings.linkedin_post_day,
            hour=settings.linkedin_post_hour,
            minute=0,
        ),
        id="weekly_linkedin",
        replace_existing=True,
    )

    # Monthly newsletter (1st of each month at 09:00 UTC)
    scheduler.add_job(
        job_monthly_newsletter,
        CronTrigger(day=1, hour=9, minute=0),
        id="monthly_newsletter",
        replace_existing=True,
    )

    return scheduler
