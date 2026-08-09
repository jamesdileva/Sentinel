"""Security endpoints — /api/v1/security.

Trigger scans as in-process scheduler jobs; findings are read via GET /findings
(docs/02 §5.6). Findings rows have no running/queued state, so polling uses the
findings list itself.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.connection import get_session
from app.repositories import ProjectRepository, SecurityRepository
from app.schemas import SecurityFindingRead
from app.schemas.security import ScanResponse
from app.services.job_scheduler import scheduler as job_scheduler

router = APIRouter(prefix="/security", tags=["security"])


def _project_or_404(project_id: str, session: Session) -> object:
    project = ProjectRepository(session).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}")
    return project


@router.post("/scan", status_code=202, response_model=ScanResponse)
def run_scan(project_id: str, session: Session = Depends(get_session)) -> ScanResponse:
    """Enqueue a full security scan for a project."""
    project = _project_or_404(project_id, session)
    job_id = job_scheduler.submit("run_security_scan", args=[project.id])
    return ScanResponse(job_id=job_id, status="queued")


@router.get("/findings", response_model=list[SecurityFindingRead])
def list_findings(
    project_id: str, session: Session = Depends(get_session)
) -> list[object]:
    """Security findings for a project (older first)."""
    _project_or_404(project_id, session)
    return SecurityRepository(session).get_by_project(project_id)
