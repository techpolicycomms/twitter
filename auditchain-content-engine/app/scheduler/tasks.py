"""
APScheduler task definitions.

Schedules:
- 06:00 UTC  →  run_news_scan   (fetch RSS, score relevance, rapid response)
- 07:00 UTC  →  run_content_gen (generate today's calendar entries)

Both jobs are AsyncIO-native and share the same database connection pool.
"""

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Job functions ──────────────────────────────────────────────────────────


async def job_news_scan() -> None:
    """
    Scheduled job: fetch RSS feeds, score for relevance, trigger rapid responses.
    Runs at 06:00 UTC daily.
    """
    logger.info(f"[SCHEDULER] Starting news scan job at {datetime.now(timezone.utc)}")

    try:
        async with AsyncSessionLocal() as db:
            from app.scanner.analyzer import run_news_scan_and_analyze

            summary = await run_news_scan_and_analyze(db)
            logger.info(f"[SCHEDULER] News scan complete: {summary}")

    except Exception as e:
        logger.error(f"[SCHEDULER] News scan job failed: {e}", exc_info=True)


async def job_content_generation() -> None:
    """
    Scheduled job: generate content for today's calendar entries.
    Runs at 07:00 UTC daily.
    """
    logger.info(
        f"[SCHEDULER] Starting content generation job at {datetime.now(timezone.utc)}"
    )

    try:
        async with AsyncSessionLocal() as db:
            from app.content.calendar import get_pending_entries_for_today
            from app.content.generator import generate_from_calendar_entry

            entries = await get_pending_entries_for_today(db)
            logger.info(f"[SCHEDULER] Processing {len(entries)} calendar entries")

            generated_count = 0
            failed_count = 0

            for entry in entries:
                try:
                    content = await generate_from_calendar_entry(entry, db)
                    await db.commit()
                    generated_count += 1
                    logger.info(
                        f"[SCHEDULER] Generated {content.platform.value} content: {entry.topic[:50]}"
                    )
                except Exception as e:
                    logger.error(
                        f"[SCHEDULER] Failed to generate content for entry {entry.id}: {e}",
                        exc_info=True,
                    )
                    await db.rollback()
                    failed_count += 1

            logger.info(
                f"[SCHEDULER] Content generation complete: "
                f"{generated_count} generated, {failed_count} failed"
            )

    except Exception as e:
        logger.error(f"[SCHEDULER] Content generation job failed: {e}", exc_info=True)


# ── Scheduler setup ────────────────────────────────────────────────────────


def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure the APScheduler instance.

    Returns a configured (but not started) AsyncIOScheduler.
    Call scheduler.start() to activate.
    """
    scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)

    # 06:00 UTC — news scan
    scheduler.add_job(
        job_news_scan,
        trigger=CronTrigger(
            hour=settings.news_scan_hour,
            minute=0,
            timezone=settings.scheduler_timezone,
        ),
        id="news_scan",
        name="Daily RSS news scan",
        replace_existing=True,
        misfire_grace_time=300,  # 5 minutes grace period
    )

    # 07:00 UTC — content generation
    scheduler.add_job(
        job_content_generation,
        trigger=CronTrigger(
            hour=settings.content_gen_hour,
            minute=0,
            timezone=settings.scheduler_timezone,
        ),
        id="content_generation",
        name="Daily content generation",
        replace_existing=True,
        misfire_grace_time=300,
    )

    logger.info(
        f"Scheduler configured: "
        f"news scan at {settings.news_scan_hour:02d}:00 UTC, "
        f"content gen at {settings.content_gen_hour:02d}:00 UTC"
    )

    return scheduler


def get_scheduler_status(scheduler: AsyncIOScheduler) -> list:
    """
    Return a list of scheduled job status dicts for the dashboard.

    Args:
        scheduler: The running AsyncIOScheduler instance.

    Returns:
        List of dicts with job_id, name, next_run_time.
    """
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "job_id": job.id,
                "name": job.name,
                "next_run_time": (
                    job.next_run_time.isoformat() if job.next_run_time else None
                ),
            }
        )
    return jobs
