"""System endpoints — /api/v1/system (Sprint 12, read-only).

Dashboard page: Ollama status (availability, models, tokens/sec from recent
generations) and Pi-hole stats (blocking state, query counts). These are
status reads only; per docs/01 Rule 2 nothing here changes server state.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db.connection import get_session
from app.services.system_service import OllamaStatus, PiHoleStatus, system_overview

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/overview")
def system_overview_endpoint(session: Session = Depends(get_session)) -> dict:
    """Aggregated home-server health: startup checks + Ollama + Pi-hole."""
    return system_overview(session)


@router.get("/ollama")
def ollama_status(session: Session = Depends(get_session)) -> dict:
    """Ollama availability, installed models, and recent generation metrics."""
    return OllamaStatus(session=session).report()


@router.get("/pihole")
def pihole_status(session: Session = Depends(get_session)) -> dict:
    """Read-only Pi-hole blocking and query statistics."""
    return PiHoleStatus().report()
