"""Lexivant Watch — FastAPI application factory."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db

logger = logging.getLogger(__name__)
_USE_SCHEDULER = os.getenv("APP_ENV", "development") != "production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lexivant Watch starting…")
    await init_db()

    scheduler = None
    if _USE_SCHEDULER:
        from app.scheduler.tasks import create_scheduler
        scheduler = create_scheduler()
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Scheduler started: %s", [j.id for j in scheduler.get_jobs()])

    yield

    if scheduler:
        scheduler.shutdown(wait=False)
    logger.info("Lexivant Watch stopped.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lexivant Watch",
        description="Intelligence Before It's Law — AI Regulatory Intelligence",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Mount static files
    from pathlib import Path

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Register routes
    from app.api.routes import router
    from app.api.cron import cron_router

    app.include_router(router)
    app.include_router(cron_router)

    # Health check endpoint (for load balancers and uptime monitors)
    from fastapi.responses import JSONResponse
    from datetime import datetime, timezone

    @app.get("/health", tags=["meta"])
    async def health_check():
        """Returns 200 with DB connectivity status."""
        from app.database import AsyncSessionLocal
        from sqlalchemy import text
        db_ok = False
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
                db_ok = True
        except Exception:
            pass
        return JSONResponse(
            status_code=200 if db_ok else 503,
            content={"status": "ok" if db_ok else "degraded", "db": "up" if db_ok else "down",
                     "ts": datetime.now(timezone.utc).isoformat()},
        )

    return app


app = create_app()
