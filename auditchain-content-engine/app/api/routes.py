"""
FastAPI API routes for the content dashboard.

Endpoints:
- GET  /                     → Dashboard HTML
- GET  /api/stats            → Dashboard statistics
- GET  /api/content          → List generated content (filterable)
- GET  /api/content/{id}     → Single content detail
- PATCH /api/content/{id}    → Update content (body, status, notes)
- POST /api/content/{id}/approve  → Approve content
- POST /api/content/{id}/reject   → Reject content
- POST /api/content/generate      → Manual generation trigger
- GET  /api/news             → List recent news items
- POST /api/news/scan        → Manual news scan trigger
- GET  /api/export           → Export approved content as Buffer JSON
- POST /api/export/buffer    → Push approved content to Buffer
- GET  /api/scheduler/status → Show scheduled job status
- GET  /api/calendar         → List calendar entries
- POST /api/calendar/import  → Import content-calendar.csv
"""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    ContentCalendarEntry,
    ContentStatus,
    GeneratedContent,
    NewsItem,
    Platform,
)
from app.schemas import (
    CalendarEntryOut,
    ContentApproveRequest,
    ContentUpdateRequest,
    DashboardStats,
    GeneratedContentOut,
    GenerateRequest,
    NewsItemOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Jinja2 templates are configured at the app level and injected here
_templates: Optional[Jinja2Templates] = None


def set_templates(templates: Jinja2Templates) -> None:
    global _templates
    _templates = templates


# ── Dashboard HTML ─────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Render the main content review dashboard."""
    stats = await _get_stats(db)

    # Recent pending content
    pending_stmt = (
        select(GeneratedContent)
        .where(GeneratedContent.status == ContentStatus.PENDING_REVIEW)
        .order_by(GeneratedContent.created_at.desc())
        .limit(20)
    )
    result = await db.execute(pending_stmt)
    pending = result.scalars().all()

    # Recent news
    news_stmt = (
        select(NewsItem)
        .order_by(NewsItem.fetched_at.desc())
        .limit(10)
    )
    news_result = await db.execute(news_stmt)
    news_items = news_result.scalars().all()

    return _templates.TemplateResponse(  # type: ignore[union-attr]
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "pending_content": pending,
            "news_items": news_items,
        },
    )


@router.get("/content/{content_id}", response_class=HTMLResponse, include_in_schema=False)
async def content_detail_page(
    request: Request, content_id: int, db: AsyncSession = Depends(get_db)
):
    """Render the content detail/edit page."""
    content = await _get_content_or_404(content_id, db)
    return _templates.TemplateResponse(  # type: ignore[union-attr]
        "content_detail.html",
        {"request": request, "content": content},
    )


@router.get("/news", response_class=HTMLResponse, include_in_schema=False)
async def news_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Render the news items page."""
    stmt = select(NewsItem).order_by(NewsItem.fetched_at.desc()).limit(50)
    result = await db.execute(stmt)
    news_items = result.scalars().all()
    return _templates.TemplateResponse(  # type: ignore[union-attr]
        "news.html",
        {"request": request, "news_items": news_items},
    )


# ── API: Stats ─────────────────────────────────────────────────────────────


@router.get("/api/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Return dashboard statistics."""
    return await _get_stats(db)


# ── API: Content ───────────────────────────────────────────────────────────


@router.get("/api/content", response_model=List[GeneratedContentOut])
async def list_content(
    status: Optional[ContentStatus] = Query(None),
    platform: Optional[Platform] = Query(None),
    source_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List generated content with optional filters.
    """
    stmt = select(GeneratedContent).order_by(GeneratedContent.created_at.desc())

    if status:
        stmt = stmt.where(GeneratedContent.status == status)
    if platform:
        stmt = stmt.where(GeneratedContent.platform == platform)
    if source_type:
        stmt = stmt.where(GeneratedContent.source_type == source_type)

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/api/content/{content_id}", response_model=GeneratedContentOut)
async def get_content(content_id: int, db: AsyncSession = Depends(get_db)):
    """Return a single content item by ID."""
    return await _get_content_or_404(content_id, db)


@router.patch("/api/content/{content_id}", response_model=GeneratedContentOut)
async def update_content(
    content_id: int,
    update: ContentUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a content item's body, status, or reviewer notes."""
    content = await _get_content_or_404(content_id, db)

    if update.body is not None:
        content.body = update.body
    if update.status is not None:
        content.status = update.status
    if update.reviewer_notes is not None:
        content.reviewer_notes = update.reviewer_notes
    if update.scheduled_for is not None:
        content.scheduled_for = update.scheduled_for

    db.add(content)
    await db.flush()
    await db.refresh(content)
    return content


@router.post("/api/content/{content_id}/approve", response_model=GeneratedContentOut)
async def approve_content(
    content_id: int,
    request: ContentApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Approve a content item for scheduling."""
    content = await _get_content_or_404(content_id, db)

    if content.status not in (ContentStatus.PENDING_REVIEW, ContentStatus.DRAFT):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve content with status '{content.status}'",
        )

    content.status = ContentStatus.APPROVED
    if request.reviewer_notes:
        content.reviewer_notes = request.reviewer_notes
    if request.scheduled_for:
        content.scheduled_for = request.scheduled_for
        content.status = ContentStatus.SCHEDULED

    db.add(content)
    await db.flush()
    await db.refresh(content)
    return content


@router.post("/api/content/{content_id}/reject", response_model=GeneratedContentOut)
async def reject_content(
    content_id: int,
    notes: str = Query(..., description="Reason for rejection"),
    db: AsyncSession = Depends(get_db),
):
    """Reject a content item with a reason."""
    content = await _get_content_or_404(content_id, db)
    content.status = ContentStatus.REJECTED
    content.reviewer_notes = notes
    db.add(content)
    await db.flush()
    await db.refresh(content)
    return content


@router.post("/api/content/generate", response_model=GeneratedContentOut)
async def generate_content(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger content generation for a given topic and platform.
    """
    from app.content.generator import generate_manual

    content = await generate_manual(
        topic=req.topic,
        platform=req.platform,
        pillar=req.content_pillar,
        additional_context=req.additional_context or "",
        db=db,
    )
    await db.commit()
    await db.refresh(content)
    return content


# ── API: News ──────────────────────────────────────────────────────────────


@router.get("/api/news", response_model=List[NewsItemOut])
async def list_news(
    min_relevance: Optional[float] = Query(None),
    rapid_response_only: bool = Query(False),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List recent news items with optional relevance filter."""
    stmt = select(NewsItem).order_by(NewsItem.fetched_at.desc())

    if min_relevance is not None:
        stmt = stmt.where(NewsItem.relevance_score >= min_relevance)
    if rapid_response_only:
        stmt = stmt.where(NewsItem.is_rapid_response.is_(True))

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/api/news/scan")
async def trigger_news_scan(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a news scan."""

    async def _run_scan():
        from app.database import AsyncSessionLocal
        from app.scanner.analyzer import run_news_scan_and_analyze

        async with AsyncSessionLocal() as scan_db:
            summary = await run_news_scan_and_analyze(scan_db)
            logger.info(f"Manual news scan complete: {summary}")

    background_tasks.add_task(_run_scan)
    return {"message": "News scan started in background"}


# ── API: Export ────────────────────────────────────────────────────────────


@router.get("/api/export")
async def export_approved(
    platform: Optional[Platform] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Export all approved content as Buffer-compatible JSON.
    """
    from app.exporters.buffer import export_to_json

    stmt = select(GeneratedContent).where(
        GeneratedContent.status.in_([ContentStatus.APPROVED, ContentStatus.SCHEDULED])
    )
    if platform:
        stmt = stmt.where(GeneratedContent.platform == platform)

    result = await db.execute(stmt)
    content_list = list(result.scalars().all())

    json_output = export_to_json(content_list)
    return JSONResponse(content=json.loads(json_output))


@router.post("/api/export/buffer")
async def push_to_buffer(
    content_ids: List[int],
    db: AsyncSession = Depends(get_db),
):
    """
    Push specific approved content items to Buffer.
    """
    from app.exporters.buffer import push_to_buffer as _push

    results = []
    for content_id in content_ids:
        content = await _get_content_or_404(content_id, db)
        if content.status not in (ContentStatus.APPROVED, ContentStatus.SCHEDULED):
            results.append(
                {"content_id": content_id, "success": False, "error": "Not approved"}
            )
            continue

        update_id = await _push(content)
        if update_id:
            content.buffer_update_id = update_id
            content.status = ContentStatus.SCHEDULED
            db.add(content)
            results.append(
                {"content_id": content_id, "success": True, "buffer_update_id": update_id}
            )
        else:
            results.append(
                {"content_id": content_id, "success": False, "error": "Buffer push failed"}
            )

    await db.flush()
    return {"results": results}


# ── API: Scheduler ─────────────────────────────────────────────────────────


@router.get("/api/scheduler/status")
async def scheduler_status(request: Request):
    """Return current scheduled job status."""
    from app.scheduler.tasks import get_scheduler_status

    scheduler = getattr(request.app.state, "scheduler", None)
    if not scheduler:
        return {"running": False, "jobs": []}

    return {"running": scheduler.running, "jobs": get_scheduler_status(scheduler)}


# ── API: Calendar ──────────────────────────────────────────────────────────


@router.get("/api/calendar", response_model=List[CalendarEntryOut])
async def list_calendar(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List content calendar entries ordered by date."""
    stmt = (
        select(ContentCalendarEntry)
        .order_by(ContentCalendarEntry.entry_date)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/api/calendar/import")
async def import_calendar(
    filepath: str = Query(default="content-calendar.csv"),
    overwrite: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    """Import or re-import the content calendar CSV."""
    from app.content.calendar import import_calendar_to_db

    try:
        inserted, skipped = await import_calendar_to_db(filepath, db, overwrite)
        return {"inserted": inserted, "skipped": skipped}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Helpers ────────────────────────────────────────────────────────────────


async def _get_content_or_404(
    content_id: int, db: AsyncSession
) -> GeneratedContent:
    stmt = select(GeneratedContent).where(GeneratedContent.id == content_id)
    result = await db.execute(stmt)
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail=f"Content {content_id} not found")
    return content


async def _get_stats(db: AsyncSession) -> DashboardStats:
    """Compute dashboard statistics from the database."""
    from datetime import date

    # Count by status
    status_stmt = select(
        GeneratedContent.status, func.count(GeneratedContent.id)
    ).group_by(GeneratedContent.status)
    status_result = await db.execute(status_stmt)
    counts = {row[0]: row[1] for row in status_result}

    # Today's news count
    today = date.today()
    news_stmt = select(func.count(NewsItem.id)).where(
        func.date(NewsItem.fetched_at) == today
    )
    news_count = (await db.execute(news_stmt)).scalar() or 0

    # Rapid response pending
    rapid_stmt = select(func.count(NewsItem.id)).where(
        NewsItem.is_rapid_response.is_(True),
        NewsItem.is_processed.is_(False),
    )
    rapid_count = (await db.execute(rapid_stmt)).scalar() or 0

    return DashboardStats(
        total_drafts=counts.get(ContentStatus.DRAFT, 0),
        pending_review=counts.get(ContentStatus.PENDING_REVIEW, 0),
        approved=counts.get(ContentStatus.APPROVED, 0),
        scheduled=counts.get(ContentStatus.SCHEDULED, 0),
        published=counts.get(ContentStatus.PUBLISHED, 0),
        rejected=counts.get(ContentStatus.REJECTED, 0),
        news_items_today=news_count,
        rapid_responses_pending=rapid_count,
    )
