"""Security endpoints — /api/v1/security.

Trigger scans as in-process scheduler jobs; findings are read via GET /findings
(docs/02 §5.6). Findings rows have no running/queued state, so polling uses the
findings list itself.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.v1._deps import project_or_404
from app.db.connection import get_session
from app.repositories import SecurityRepository
from app.schemas import SecurityClearRead, SecurityFindingRead
from app.schemas.security import ScanResponse
from app.services.job_scheduler import scheduler as job_scheduler

router = APIRouter(prefix="/security", tags=["security"])


@router.post("/scan", status_code=202, response_model=ScanResponse)
def run_scan(project_id: str, session: Session = Depends(get_session)) -> ScanResponse:
    """Enqueue a full security scan for a project."""
    project = project_or_404(project_id, session)
    job_id = job_scheduler.submit("run_security_scan", args=[project.id])
    return ScanResponse(job_id=job_id, status="queued")


@router.post("/scan-all", status_code=202, response_model=ScanResponse)
def run_scan_all(session: Session = Depends(get_session)) -> ScanResponse:
    """Enqueue a security scan for every indexed project."""
    job_id = job_scheduler.submit("run_security_scan_all")
    return ScanResponse(job_id=job_id, status="queued")


@router.get("/findings", response_model=list[SecurityFindingRead])
def list_findings(
    project_id: str, session: Session = Depends(get_session)
) -> list[object]:
    """Security findings for a project (older first)."""
    project_or_404(project_id, session)
    return SecurityRepository(session).get_by_project(project_id)


@router.delete("/findings", response_model=SecurityClearRead)
def clear_resolved(
    project_id: str, session: Session = Depends(get_session)
) -> SecurityClearRead:
    """Delete a project's *resolved* findings (v1.17.7.7). Open findings are
    never touched. Returns the number of rows deleted — the resolved rows are
    the stale leftovers of previous scans that spam the timeline."""
    project_or_404(project_id, session)
    deleted = SecurityRepository(session).delete_resolved(project_id)
    # v1.17.18.4 (audit2 D7): the repository only flushes now — commit here.
    session.commit()
    return SecurityClearRead(deleted=deleted)
