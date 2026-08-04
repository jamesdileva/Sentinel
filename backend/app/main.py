"""Project Sentinel — FastAPI application entry point.

Sprint 1 scope: health endpoints, CORS, exception handling, CLI-compatible server.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.connection import check_db

setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Local-first personal software operations platform.",
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
