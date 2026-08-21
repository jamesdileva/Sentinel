"""Project endpoints — /api/v1/projects.

Consumed by the dashboard (Sprint 6). Reads flow through ProjectRepository;
there is no create/update here — projects are indexed via the CLI/IndexerService
(docs/02 §3.1, §5.1).
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.v1._deps import project_or_404
from app.db.connection import get_session
from app.repositories import ProjectFileRepository, ProjectRepository
from app.schemas import ProjectFileRead, ProjectList, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=ProjectList)
def list_projects(session: Session = Depends(get_session)) -> ProjectList:
    """List all indexed projects."""
    projects = ProjectRepository(session).list()
    return ProjectList(projects=projects, total=len(projects))


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, session: Session = Depends(get_session)) -> object:
    """Get a single project by id."""
    return project_or_404(project_id, session)


@router.get("/{project_id}/files", response_model=list[ProjectFileRead])
def list_project_files(
    project_id: str,
    limit: int = Query(500, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[object]:
    """List the indexed files of a project. Capped (audit2 C8): a noisy tree
    can hold tens of thousands of indexed files."""
    project = project_or_404(project_id, session)
    return ProjectFileRepository(session).get_by_project(project.id, limit=limit)
