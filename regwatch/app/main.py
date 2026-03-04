"""RegWatch FastAPI application factory with lifespan scheduler."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.scheduler.tasks import create_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("RegWatch starting up...")
    await init_db()
    scheduler = create_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("Scheduler started. Jobs: %s", [j.id for j in scheduler.get_jobs()])
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("RegWatch shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="RegWatch",
        description="AI Regulatory Intelligence for AuditChain's Markets",
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

    return app


app = create_app()
