"""Project Sentinel — FastAPI application entry point.

Sprint 1 scope: health endpoints, CORS, exception handling, CLI-compatible server.
Sprint 2: database initialization on startup (lifespan).
Sprint 3: background repository discovery scan on startup.
Sprint 16: single-process runtime — the API also serves the built dashboard
(SPA) from `backend/app/static`, and the in-process scheduler replaces Celery.
"""

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.builds import router as builds_router
from app.api.v1.observatory import router as observatory_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.projects import router as projects_router
from app.api.v1.rag import router as rag_router
from app.api.v1.security import router as security_router
from app.api.v1.system import router as system_router
from app.api.v1.tests import router as tests_router
from app.api.v1.world_sim import router as world_sim_router
from app.api.v1.ws import router as ws_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.connection import check_db, get_engine, init_db
from app.services.job_scheduler import scheduler
from app.services.startup_check import run_startup_checks

setup_logging()
logger = get_logger(__name__)

# The committed, release-shipped build (scripts/build.py --dist stages into it).
STATIC_DIR = Path(__file__).resolve().parent / "static"
# Dev convenience: a fresh clone with no staged build yet can serve frontend/dist.
DEV_DIST = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"

DASHBOARD_DIR = (
    STATIC_DIR if STATIC_DIR.is_dir() else (DEV_DIST if DEV_DIST.is_dir() else None)
)
DASHBOARD_INDEX = (
    Path(DASHBOARD_DIR) / "index.html" if DASHBOARD_DIR is not None else None
)


def _background_initial_scan() -> None:
    """Discover and index known repositories (.git) under watch dirs.

    Runs in a daemon thread so server startup never blocks on indexing.
    Indexing is deterministic and bounded: only dirs containing `.git`.
    """
    from sqlmodel import Session

    from app.services.indexer import IndexerService

    try:
        with Session(get_engine()) as session:
            projects = IndexerService(session).scan_all_projects()
        logger.info("Initial scan complete: %d project(s) indexed", len(projects))
    except Exception:
        logger.exception("Background initial scan failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    run_startup_checks()
    if settings.scheduler_enabled:
        scheduler.start()
        logger.info("In-process scheduler started")
    if settings.auto_scan_on_startup:
        threading.Thread(
            target=_background_initial_scan, daemon=True, name="sentinel-scan"
        ).start()
        logger.info("Background discovery scan started")
    logger.info("Application startup complete")
    yield
    scheduler.shutdown()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Local-first personal software operations platform.",
    lifespan=lifespan,
)


@app.get("/", tags=["system"])
def root():
    """Serve the dashboard; health JSON only when no build exists."""
    if DASHBOARD_INDEX is not None and DASHBOARD_INDEX.is_file():
        return FileResponse(DASHBOARD_INDEX)
    return {"status": "ok"}


@app.get("/health", tags=["system"])
def health() -> dict:
    """Enhanced system health: app version and database reachability."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.version,
        "database": {"reachable": check_db(), "path": str(settings.db_path)},
    }


@app.get("/api/v1/health", tags=["system"])
def health_v1() -> dict:
    return health()


app.include_router(projects_router, prefix="/api/v1")
app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(observatory_router, prefix="/api/v1")
app.include_router(builds_router, prefix="/api/v1")
app.include_router(tests_router, prefix="/api/v1")
app.include_router(security_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(rag_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
if settings.world_sim_enabled:
    app.include_router(world_sim_router, prefix="/api/v1")

# SPA dashboard (Sprint 16): the same origin serves the built frontend, so one
# process = API + WebSocket + dashboard with no nginx and no CORS. Served from
# backend/app/static (the staged, shipped build). Mounted after the routers so
# /api/* and health routes always win; unknown paths fall back to index.html
# (client-side routing).
if DASHBOARD_DIR is not None:
    assets_dir = DASHBOARD_DIR / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="frontend-assets",
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        candidate = (DASHBOARD_DIR / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(DASHBOARD_DIR.resolve()):
            return FileResponse(candidate)
        return FileResponse(DASHBOARD_INDEX)

    logger.info("Serving dashboard from %s", DASHBOARD_DIR)
else:
    logger.info(
        "no dashboard build found (backend/app/static) — API only "
        "(run `scripts/build.py --dist`)"
    )
