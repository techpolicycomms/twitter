"""FastAPI routes for Lexivant Watch dashboard and API."""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.analyzer import analyze_all_pending
from app.database import get_db
from app.models import ImpactLevel, RegulationItem, Report, ReportType, ScrapeRun
from app.notifications.alert_manager import process_pending_alerts
from app.reports.generator import (
    generate_daily_digest,
    generate_monthly_newsletter,
    generate_weekly_linkedin,
)
from app.scrapers import ALL_SCRAPERS

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    region: str | None = None,
    impact: str | None = None,
    page: int = Query(default=1, ge=1),
):
    page_size = 20
    query = select(RegulationItem).where(RegulationItem.analyzed == True)  # noqa: E712

    if region:
        query = query.where(RegulationItem.region == region)
    if impact:
        try:
            query = query.where(RegulationItem.impact_level == ImpactLevel(impact.upper()))
        except ValueError:
            pass

    query = query.order_by(
        desc(RegulationItem.impact_level), desc(RegulationItem.relevance_score)
    )

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()

    stats_result = await db.execute(
        select(RegulationItem.impact_level, func.count(RegulationItem.id))
        .where(RegulationItem.analyzed == True, RegulationItem.is_relevant == True)  # noqa: E712
        .group_by(RegulationItem.impact_level)
    )
    stats = {row[0].value if row[0] else "UNKNOWN": row[1] for row in stats_result.all()}

    regions_result = await db.execute(
        select(RegulationItem.region).distinct().order_by(RegulationItem.region)
    )
    regions = [r[0] for r in regions_result.all()]

    recent_run = await db.execute(
        select(ScrapeRun).order_by(desc(ScrapeRun.started_at)).limit(1)
    )
    last_run = recent_run.scalar()

    # 24h item count
    last_24h_result = await db.execute(
        select(func.count(RegulationItem.id)).where(
            RegulationItem.scraped_at >= datetime.now(timezone.utc) - timedelta(hours=24),
            RegulationItem.is_relevant == True,  # noqa: E712
        )
    )
    last_24h = last_24h_result.scalar() or 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "items": items,
            "stats": stats,
            "regions": regions,
            "filter_region": region,
            "filter_impact": impact,
            "page": page,
            "total": total,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "last_run": last_run,
            "last_24h": last_24h,
        },
    )


@router.get("/item/{item_id}", response_class=HTMLResponse)
async def item_detail(request: Request, item_id: int, db: AsyncSession = Depends(get_db)):
    import json

    result = await db.execute(select(RegulationItem).where(RegulationItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        action_items = json.loads(item.action_items or "[]")
    except json.JSONDecodeError:
        action_items = []

    try:
        keywords = json.loads(item.keywords or "[]")
    except json.JSONDecodeError:
        keywords = []

    return templates.TemplateResponse(
        "item_detail.html",
        {"request": request, "item": item, "action_items": action_items, "keywords": keywords},
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).order_by(desc(Report.created_at)).limit(50))
    reports = result.scalars().all()
    return templates.TemplateResponse("reports.html", {"request": request, "reports": reports})


@router.get("/reports/{report_id}", response_class=HTMLResponse)
async def report_detail(request: Request, report_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return templates.TemplateResponse("report_detail.html", {"request": request, "report": report})


# ── API ────────────────────────────────────────────────────────────────────


def _bg_scrape(source_key: str | None = None):
    async def _run():
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            scrapers = (
                [s for s in ALL_SCRAPERS if s.source_key == source_key]
                if source_key
                else ALL_SCRAPERS
            )
            for Cls in scrapers:
                try:
                    await Cls().scrape(session)
                except Exception as exc:
                    logger.error("%s: %s", Cls.source_key, exc)

    return _run


@router.post("/api/scrape")
async def trigger_scrape(background_tasks: BackgroundTasks, source_key: str | None = None):
    background_tasks.add_task(_bg_scrape(source_key))
    return {"status": "Scrape started", "source_key": source_key or "all"}


@router.post("/api/analyze")
async def trigger_analysis(background_tasks: BackgroundTasks):
    async def _run():
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            await analyze_all_pending(s)

    background_tasks.add_task(_run)
    return {"status": "Analysis started"}


@router.post("/api/alerts/process")
async def trigger_alerts(background_tasks: BackgroundTasks):
    async def _run():
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            await process_pending_alerts(s)

    background_tasks.add_task(_run)
    return {"status": "Alert processing started"}


@router.post("/api/reports/digest")
async def trigger_digest(background_tasks: BackgroundTasks):
    async def _run():
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            await generate_daily_digest(s)

    background_tasks.add_task(_run)
    return {"status": "Daily digest generation started"}


@router.post("/api/reports/linkedin")
async def trigger_linkedin(background_tasks: BackgroundTasks):
    async def _run():
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            await generate_weekly_linkedin(s)

    background_tasks.add_task(_run)
    return {"status": "LinkedIn post generation started"}


@router.post("/api/reports/newsletter")
async def trigger_newsletter(background_tasks: BackgroundTasks):
    async def _run():
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            await generate_monthly_newsletter(s)

    background_tasks.add_task(_run)
    return {"status": "Newsletter generation started"}


@router.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = await db.execute(select(func.count(RegulationItem.id)))
    analyzed = await db.execute(
        select(func.count(RegulationItem.id)).where(RegulationItem.analyzed == True)  # noqa: E712
    )
    relevant = await db.execute(
        select(func.count(RegulationItem.id)).where(
            RegulationItem.analyzed == True, RegulationItem.is_relevant == True  # noqa: E712
        )
    )
    high = await db.execute(
        select(func.count(RegulationItem.id)).where(
            RegulationItem.impact_level == ImpactLevel.HIGH
        )
    )
    last_24h = await db.execute(
        select(func.count(RegulationItem.id)).where(
            RegulationItem.scraped_at >= datetime.now(timezone.utc) - timedelta(hours=24)
        )
    )
    return {
        "total_items": total.scalar(),
        "analyzed": analyzed.scalar(),
        "relevant": relevant.scalar(),
        "high_impact": high.scalar(),
        "last_24h": last_24h.scalar(),
    }


@router.get("/api/items")
async def list_items(
    region: str | None = None,
    impact: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(RegulationItem).where(
        RegulationItem.analyzed == True, RegulationItem.is_relevant == True  # noqa: E712
    )
    if region:
        query = query.where(RegulationItem.region == region)
    if impact:
        query = query.where(RegulationItem.impact_level == ImpactLevel(impact.upper()))

    query = (
        query.order_by(desc(RegulationItem.impact_level), desc(RegulationItem.relevance_score))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    return [
        {
            "id": i.id,
            "region": i.region,
            "source_name": i.source_name,
            "title": i.title,
            "url": i.url,
            "impact_level": i.impact_level.value if i.impact_level else None,
            "relevance_score": i.relevance_score,
            "summary": i.ai_summary,
            "published_at": i.published_at.isoformat() if i.published_at else None,
            "scraped_at": i.scraped_at.isoformat(),
        }
        for i in items
    ]


# ── SSE endpoint for real-time dashboard updates ─────────────────────────────
# Pattern from fastapi-htmx-tailwind-example (101★) + sse-starlette
# The dashboard uses: hx-ext="sse" hx-sse-connect="/api/stream"
# to receive partial HTML fragments pushed from the server

import asyncio as _asyncio
from sse_starlette.sse import EventSourceResponse


@router.get("/api/stream")
async def stream_events(request: Request, db: AsyncSession = Depends(get_db)):
    """
    SSE endpoint — broadcasts live counts and new HIGH-impact alerts.
    HTMX client subscribes via hx-ext="sse" hx-sse-connect="/api/stream"
    and swaps only the affected dashboard elements (stat counters, alert banner).
    """
    async def _event_generator():
        while True:
            if await request.is_disconnected():
                break

            # Push current HIGH-impact unalerted count every 30s
            try:
                from sqlalchemy import func as _func
                count_result = await db.execute(
                    select(_func.count(RegulationItem.id)).where(
                        RegulationItem.impact_level == ImpactLevel.HIGH,
                        RegulationItem.alert_sent == False,  # noqa: E712
                        RegulationItem.analyzed == True,    # noqa: E712
                    )
                )
                count = count_result.scalar_one()
                yield {
                    "event": "high-impact-count",
                    "data": str(count),
                }
            except Exception:
                pass

            await _asyncio.sleep(30)

    return EventSourceResponse(_event_generator())
