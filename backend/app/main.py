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

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.builds import router as builds_router
from app.api.v1.observatory import router as observatory_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.projects import router as projects_router
from app.api.v1.rag import router as rag_router
from app.api.v1.security import router as security_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.settings import router as settings_router
from app.api.v1.system import router as system_router
from app.api.v1.testers import router as testers_router
from app.api.v1.tests import router as tests_router
from app.api.v1.world_sim import router as world_sim_router
from app.api.v1.ws import router as ws_router
from app.core.config import settings
from app.core.logging import attach_file_logging, get_logger, setup_logging
from app.db.connection import check_db, get_engine, init_db
from app.services.chroma_manager import RagIndexError
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
    """Startup pass (v1.17.1): sync → scan → auto knowledge-index.

    Runs in a daemon thread so server startup never blocks:
    * If a GitHub token is configured, one repo sync runs first (clone/pull),
      so newly added repos exist before the scan walks the watch dirs
      (*then* the daily beat takes over — see SENTINEL_SYNC_INTERVAL_MINUTES).
      Tokenless (v1.17.7: the supported local-only setup) skips this silently —
      local projects are indexed straight from the watch dirs.
    * Discovery scan of known repositories (.git) under watch dirs.
    * When `auto_index_knowledge` is on, projects with unembedded files are
      queued for RAG indexing (Ollama-gated). Both outcomes are published on
      the activity bus so the dashboard shows what happened.
    """
    from sqlmodel import Session

    from app.services.indexer import IndexerService

    try:
        from app.services import activity_bus
        from app.services.sync_service import RepoSyncService
        from app.tasks import sync_tasks

        if RepoSyncService().configured:
            try:
                sync_tasks.run_repo_sync()
            except Exception:  # noqa: BLE001 — startup must survive a bad sync
                logger.exception("Startup repo sync failed")
                activity_bus.publish_event(
                    "sync", "Startup repo sync failed", data={"configured": True}
                )
        else:
            logger.info("Startup repo sync skipped (no SENTINEL_GITHUB_TOKEN)")
    except Exception:  # noqa: BLE001
        logger.exception("Startup sync step failed")

    try:
        with Session(get_engine()) as session:
            projects = IndexerService(session).scan_all_projects()
        logger.info("Initial scan complete: %d project(s) indexed", len(projects))
    except Exception:
        logger.exception("Background initial scan failed")
        return
    if settings.auto_index_knowledge and projects:
        try:
            from app.services import activity_bus
            from app.services.sync_service import queue_knowledge_index_unembedded

            knowledge = queue_knowledge_index_unembedded()
            queued = knowledge.get("queued", 0)
            skipped = knowledge.get("skipped")
            if queued:
                activity_bus.publish_event(
                    "knowledge",
                    f"Auto knowledge indexing queued {queued} project(s)",
                    detail="Newly discovered projects with unembedded files.",
                    data={"queued": queued},
                )
            elif skipped == "ollama-unavailable":
                activity_bus.publish_event(
                    "knowledge",
                    "Auto knowledge indexing skipped — Ollama unavailable",
                    data={"queued": 0},
                )
            logger.info(
                "Auto knowledge indexing: %d job(s) queued (%s)",
                queued,
                skipped or "ok",
            )
        except Exception:  # noqa: BLE001 — startup must never fail on this
            logger.exception("Auto knowledge indexing failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    attach_file_logging()  # uvicorn replaced root handlers; keep the run log
    init_db()
    from app.services.portfolio_service import refresh_all_scores

    refresh_all_scores()  # v1.17.18.0: self-heal rows cached pre-screenshots
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.services.app_sessions import AppSessionService

    with Session(get_engine()) as startup_session:
        swept = AppSessionService(startup_session).sweep_expired_screenshots()
    if swept:
        logger.info("Screenshot retention sweep removed %d expired file(s)", swept)
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


@app.exception_handler(RagIndexError)
async def rag_index_error_handler(request: Request, exc: RagIndexError) -> JSONResponse:
    """Damaged knowledge index → 503 with a rebuild hint (v1.17.6).

    ChromaDB raises InternalError when its on-disk HNSW segment files are
    gone (interrupted write / killed process); plumbing it through as a
    raw 500 hides the only recovery: drop collections and re-index."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def rag_payload_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Log RAG payload rejections (v1.17.13): uvicorn's access log records
    only the 422 status, so a failed chat save is invisible without the
    body. Scoped to the RAG payload endpoints; every other 422 keeps the
    standard response shape."""
    if request.url.path.startswith(("/api/v1/rag/chat", "/api/v1/rag/query")):
        body = (await request.body())[:2000].decode("utf-8", errors="replace")
        logger.warning(
            "RAG payload rejected on %s: %s body=%s",
            request.url.path,
            exc.errors(),
            body,
        )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


app.include_router(projects_router, prefix="/api/v1")
app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(observatory_router, prefix="/api/v1")
app.include_router(builds_router, prefix="/api/v1")
app.include_router(tests_router, prefix="/api/v1")
app.include_router(testers_router, prefix="/api/v1")
app.include_router(security_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
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
