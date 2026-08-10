"""System endpoints — /api/v1/system (Sprint 12, read-only).

Dashboard page: Ollama status (availability, models, tokens/sec from recent
generations) and sync status. These are status reads only; per docs/01 Rule 2
nothing here changes server state.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.config import settings
from app.db.connection import get_session
from app.services.sync_service import latest_sync_run
from app.services.system_service import OllamaStatus, system_overview

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/overview")
def system_overview_endpoint(session: Session = Depends(get_session)) -> dict:
    """Aggregated home-server health: startup checks + Ollama."""
    return system_overview(session)


@router.get("/sync")
def sync_status(session: Session = Depends(get_session)) -> dict:
    """GitHub repo-sync configuration + outcome of the last run (read-only)."""
    return {
        "configured": bool(settings.github_token),
        "last_run": latest_sync_run(session),
        "interval_minutes": settings.sync_interval_minutes,
    }


@router.get("/ollama")
def ollama_status(session: Session = Depends(get_session)) -> dict:
    """Ollama availability, installed models, and recent generation metrics."""
    return OllamaStatus(session=session).report()


@router.get("/activity")
def activity(limit: int = 50) -> dict:
    """Tail of the persisted activity stream (newest first)."""
    from app.services import activity_bus

    return {"events": activity_bus.recent_events(limit=min(limit, 500))}
