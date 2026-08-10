"""System endpoints — /api/v1/system (Sprint 12, read-only).

Dashboard page: Ollama status (availability, models, tokens/sec from recent
generations) and sync status. These are status reads only; per docs/01 Rule 2
nothing here changes server state — except POST /system/sync, which queues the
deterministic repo-sync job on explicit user action (the header button).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.config import settings
from app.db.connection import get_session
from app.schemas import JobEnvelope
from app.services.job_scheduler import scheduler
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


@router.post("/sync", status_code=202, response_model=JobEnvelope)
def sync_now() -> JobEnvelope:
    """Queue a repo sync now (header "Sync now" button, v1.17.1).

    State-changing, but Rule 3-deterministic: it only clones/pulls known
    repos and re-indexes — no AI, no irreversible action. Rejected with 409
    when SENTINEL_GITHUB_TOKEN is not configured.
    """
    if not settings.github_token:
        raise HTTPException(
            status_code=409,
            detail="SENTINEL_GITHUB_TOKEN is not configured — repo sync cannot run",
        )
    job_id = scheduler.submit("run_repo_sync")
    return JobEnvelope(job_id=job_id, status="queued")


@router.get("/ollama")
def ollama_status(session: Session = Depends(get_session)) -> dict:
    """Ollama availability, installed models, and recent generation metrics."""
    return OllamaStatus(session=session).report()


@router.get("/activity")
def activity(limit: int = 50) -> dict:
    """Tail of the persisted activity stream (newest first)."""
    from app.services import activity_bus

    return {"events": activity_bus.recent_events(limit=min(limit, 500))}
