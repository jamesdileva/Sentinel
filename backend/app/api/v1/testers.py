"""Tester endpoints — /api/v1/testers (later.md Tier 2).

GET  /testers/{project_id} — tester descriptor or 404 ("No tester").
POST /testers/run         — enqueue a tester run (JobEnvelope; results land
                            in an AppSession, found by polling the sessions
                            API).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.connection import get_session
from app.repositories import ProjectRepository
from app.schemas import JobEnvelope, TesterDescriptor
from app.schemas.tester import TesterRunRequest
from app.services.job_scheduler import scheduler as job_scheduler
from app.services.tester_runner import TesterRunner

router = APIRouter(prefix="/testers", tags=["testers"])


def _project_or_404(project_id: str, session: Session):
    project = ProjectRepository(session).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}")
    return project


@router.get("/{project_id}", response_model=TesterDescriptor)
def get_tester(project_id: str, session: Session = Depends(get_session)):
    project = _project_or_404(project_id, session)
    descriptor = TesterRunner(session).describe(project)
    if descriptor is None:
        raise HTTPException(status_code=404, detail=f"No tester for {project.name}")
    return descriptor


@router.post("/run", status_code=202, response_model=JobEnvelope)
def run_tester(
    payload: TesterRunRequest, session: Session = Depends(get_session)
) -> JobEnvelope:
    project = _project_or_404(payload.project_id, session)
    if TesterRunner(session).describe(project) is None:
        raise HTTPException(status_code=404, detail=f"No tester for {project.name}")
    job_id = job_scheduler.submit("run_tester", args=[project.id])
    return JobEnvelope(job_id=job_id, status="queued")
