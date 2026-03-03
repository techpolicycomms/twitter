"""
AuditChain Content Engine — FastAPI application entry point.

Starts:
- FastAPI app with Jinja2 dashboard
- APScheduler for cron jobs (news scan + content generation)
- PostgreSQL connection via SQLAlchemy async
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router, set_templates
from app.config import get_settings
from app.database import create_all_tables
from app.scheduler.tasks import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
settings = get_settings()

BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs setup on startup and cleanup on shutdown.
    """
    # ── Startup ───────────────────────────────────────────
    logger.info("Starting AuditChain Content Engine")

    # Create database tables
    await create_all_tables()
    logger.info("Database tables ready")

    # Import the content calendar on startup
    try:
        from app.database import AsyncSessionLocal
        from app.content.calendar import import_calendar_to_db

        async with AsyncSessionLocal() as db:
            csv_path = BASE_DIR / "content-calendar.csv"
            if csv_path.exists():
                inserted, skipped = await import_calendar_to_db(csv_path, db)
                await db.commit()
                logger.info(
                    f"Calendar imported: {inserted} new entries, {skipped} existing"
                )
    except Exception as e:
        logger.warning(f"Calendar auto-import skipped: {e}")

    # Start the scheduler
    scheduler = create_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("APScheduler started")

    yield

    # ── Shutdown ──────────────────────────────────────────
    logger.info("Shutting down AuditChain Content Engine")
    if hasattr(app.state, "scheduler") and app.state.scheduler.running:
        app.state.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def create_app() -> FastAPI:
    """Factory function — creates and configures the FastAPI application."""
    app = FastAPI(
        title="AuditChain Content Engine",
        description=(
            "AI-powered social media content generation and scheduling "
            "for the AuditChain platform."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # Static files
    static_dir = BASE_DIR / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Jinja2 templates
    templates_dir = BASE_DIR / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    set_templates(templates)

    # Register routes
    app.include_router(router)

    return app


app = create_app()
