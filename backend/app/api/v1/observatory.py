"""Observatory endpoints — /api/v1/observatory.

Read-only overviews: shared-technology galaxy graph, activity timeline, and per
project architecture trees (docs/02 §2.11, §14.6). All deterministic; no AI.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.db.connection import get_session
from app.schemas import ArchitectureNode, GalaxyGraph, Timeline
from app.services.observatory_service import ObservatoryService

router = APIRouter(prefix="/observatory", tags=["observatory"])


def get_observatory_service(
    session: Session = Depends(get_session),
) -> ObservatoryService:
    """FastAPI dependency so tests can override the service with a temp DB."""
    return ObservatoryService(session)


@router.get("/galaxy", response_model=GalaxyGraph)
def galaxy(
    service: ObservatoryService = Depends(get_observatory_service),
) -> GalaxyGraph:
    """Shared-technology graph: project nodes linked to tech nodes (2+ projects)."""
    return service.galaxy()


@router.get("/timeline", response_model=Timeline)
def timeline(
    days: int = 365,
    kind: str | None = None,
    project_id: str | None = None,
    offset: int = 0,
    limit: int = Query(500, ge=1, le=1000),
    service: ObservatoryService = Depends(get_observatory_service),
) -> Timeline:
    """Chronological activity (creation, commits, builds, tests, findings).

    v1.17.9: `kind` accepts a comma-separated list, `project_id` narrows to
    one project, and `offset`/`limit` page through the window — the response
    carries `has_more`.
    """
    kinds = [k.strip() for k in kind.split(",") if k.strip()] if kind else None
    return service.timeline(
        days=days,
        kinds=kinds,
        project_id=project_id,
        offset=offset,
        limit=limit,
    )


@router.get("/architecture/{project_id}", response_model=ArchitectureNode)
def architecture(
    project_id: str,
    service: ObservatoryService = Depends(get_observatory_service),
) -> ArchitectureNode:
    """Nested component tree for a project, derived from indexed file paths."""
    try:
        return service.architecture(project_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Unknown project: {project_id}"
        ) from None
