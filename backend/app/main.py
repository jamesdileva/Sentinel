"""Project Sentinel — FastAPI application entry point.

Sprint 1 scope: health endpoints, CORS, exception handling, CLI-compatible server.
Sprint 2: database initialization on startup (lifespan).
Sprint 3: background repository discovery scan on startup.
"""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.builds import router as builds_router
from app.api.v1.observatory import router as observatory_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.projects import router as projects_router
from app.api.v1.rag import router as rag_router
from app.api.v1.security import router as security_router
from app.api.v1.tests import router as tests_router
from app.api.v1.world_sim import router as world_sim_router
from app.api.v1.ws import router as ws_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.connection import check_db, get_engine, init_db

setup_logging()
logger = get_logger(__name__)


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
    if settings.auto_scan_on_startup:
        threading.Thread(
            target=_background_initial_scan, daemon=True, name="sentinel-scan"
        ).start()
        logger.info("Background discovery scan started")
    logger.info("Application startup complete")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Local-first personal software operations platform.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["system"])
def root() -> dict:
    """Health check root endpoint."""
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
app.include_router(rag_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
if settings.world_sim_enabled:
    app.include_router(world_sim_router, prefix="/api/v1")
