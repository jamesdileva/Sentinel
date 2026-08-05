"""Project endpoints — /api/v1/projects.

Consumed by the dashboard (Sprint 6). Reads flow through ProjectRepository;
there is no create/update here — projects are indexed via the CLI/IndexerService
(docs/02 §3.1, §5.1).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.connection import get_session
from app.repositories import ProjectFileRepository, ProjectRepository
from app.schemas import ProjectFileRead, ProjectList, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_project_or_404(project_id: str, session: Session) -> object:
    project = ProjectRepository(session).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}")
    return project


@router.get("/", response_model=ProjectList)
def list_projects(session: Session = Depends(get_session)) -> ProjectList:
    """List all indexed projects."""
    projects = ProjectRepository(session).list()
    return ProjectList(projects=projects, total=len(projects))


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, session: Session = Depends(get_session)) -> object:
    """Get a single project by id."""
    return _get_project_or_404(project_id, session)


@router.get("/{project_id}/files", response_model=list[ProjectFileRead])
def list_project_files(
    project_id: str, session: Session = Depends(get_session)
) -> list[object]:
    """List the indexed files of a project."""
    project = _get_project_or_404(project_id, session)
    return ProjectFileRepository(session).get_by_project(project.id)
