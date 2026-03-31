"""Vercel Cron Job endpoints — secured with CRON_SECRET header."""
import logging
import os

from fastapi import APIRouter, Header, HTTPException

from app.analysis.analyzer import analyze_all_pending
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
cron_router = APIRouter(prefix="/api/cron", tags=["cron"])

CRON_SECRET = os.getenv("CRON_SECRET", "")
APP_ENV = os.getenv("APP_ENV", "development")

if not CRON_SECRET and APP_ENV == "production":
    raise RuntimeError("CRON_SECRET must be set in production")

if not CRON_SECRET:
    logger.warning("CRON_SECRET is not set — cron endpoints are unauthenticated (dev mode only)")


def _verify_cron(authorization: str | None):
    """Verify Vercel cron secret. Unauthenticated access is only allowed when CRON_SECRET is unset in dev."""
    if not CRON_SECRET:
        return  # dev mode, no auth
    expected = f"Bearer {CRON_SECRET}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@cron_router.get("/scrape")
async def cron_scrape(authorization: str | None = Header(default=None)):
    """Daily scrape: all sources → analyze → alerts. Called by Vercel at 06:00 UTC."""
    _verify_cron(authorization)
    total_new = 0

    async with AsyncSessionLocal() as db:
        for ScraperClass in ALL_SCRAPERS:
            try:
                scraper = ScraperClass()
                new_items = await scraper.scrape(db)
                total_new += len(new_items)
            except Exception as exc:
                logger.error("[cron/scrape] %s failed: %s", ScraperClass.source_key, exc)

    if total_new > 0:
        async with AsyncSessionLocal() as db:
            analyzed = await analyze_all_pending(db)
        async with AsyncSessionLocal() as db:
            alerts_sent = await process_pending_alerts(db)
        return {"new_items": total_new, "analyzed": analyzed, "alerts_sent": alerts_sent}

    return {"new_items": 0, "analyzed": 0, "alerts_sent": 0}


@cron_router.get("/digest")
async def cron_digest(authorization: str | None = Header(default=None)):
    """Daily digest email. Called by Vercel at 08:00 UTC."""
    _verify_cron(authorization)
    from app.config import settings

    try:
        async with AsyncSessionLocal() as db:
            report = await generate_daily_digest(db)
    except Exception as exc:
        logger.error("[cron/digest] Failed to generate daily digest: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate digest")

    if report and settings.team_email_recipients:
        from datetime import datetime, timezone

        sent = await send_report_email(report, settings.team_email_recipients)
        if sent:
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                from app.models import Report

                result = await db.execute(select(Report).where(Report.id == report.id))
                r = result.scalar_one()
                r.sent = True
                r.sent_at = datetime.now(timezone.utc)
                await db.commit()
        return {"report_id": report.id, "sent": sent}

    return {"report_id": None, "sent": False}


@cron_router.get("/linkedin")
async def cron_linkedin(authorization: str | None = Header(default=None)):
    """Weekly LinkedIn post. Called by Vercel every Monday 09:00 UTC."""
    _verify_cron(authorization)

    try:
        async with AsyncSessionLocal() as db:
            report = await generate_weekly_linkedin(db)
    except Exception as exc:
        logger.error("[cron/linkedin] Failed to generate LinkedIn post: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate LinkedIn post")

    if report:
        return {"report_id": report.id, "chars": len(report.content_text or "")}
    return {"report_id": None}


@cron_router.get("/newsletter")
async def cron_newsletter(authorization: str | None = Header(default=None)):
    """Monthly newsletter. Called by Vercel on 1st of month 09:00 UTC."""
    _verify_cron(authorization)
    from app.config import settings

    try:
        async with AsyncSessionLocal() as db:
            report = await generate_monthly_newsletter(db)
    except Exception as exc:
        logger.error("[cron/newsletter] Failed to generate newsletter: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate newsletter")

    if report:
        if settings.newsletter_list_id:
            from app.notifications.email import send_newsletter_via_sendgrid_list

            await send_newsletter_via_sendgrid_list(report, settings.newsletter_list_id)
        elif settings.team_email_recipients:
            await send_report_email(report, settings.team_email_recipients)
        return {"report_id": report.id, "items": report.item_count}

    return {"report_id": None}
