"""Tester endpoints — /api/v1/testers (later.md Tier 2).

GET  /testers/{project_id} — tester descriptor or 404 ("No tester").
POST /testers/run         — enqueue a tester run (JobEnvelope; results land
                            in an AppSession, found by polling the sessions
                            API).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.v1._deps import project_or_404
from app.db.connection import get_session
from app.schemas import JobEnvelope, TesterDescriptor
from app.schemas.tester import TesterRunRequest
from app.services.job_scheduler import scheduler as job_scheduler
from app.services.project_operations import active_operations
from app.services.tester_runner import TesterRunner

router = APIRouter(prefix="/testers", tags=["testers"])


@router.get("/{project_id}", response_model=TesterDescriptor)
def get_tester(project_id: str, session: Session = Depends(get_session)):
    project = project_or_404(project_id, session)
    descriptor = TesterRunner(session).describe(project)
    if descriptor is None:
        raise HTTPException(status_code=404, detail=f"No tester for {project.name}")
    return descriptor


@router.post("/run", status_code=202, response_model=JobEnvelope)
def run_tester(
    payload: TesterRunRequest, session: Session = Depends(get_session)
) -> JobEnvelope:
    """v1.17.19.10 (audit A7): testers drive the app's real UI, so a tester
    never starts alongside a build or another tester — the matrix refuses
    both directions. Driving two click-throughs against one app produces
    screenshots that belong to neither."""
    project = project_or_404(payload.project_id, session)
    if TesterRunner(session).describe(project) is None:
        raise HTTPException(status_code=404, detail=f"No tester for {project.name}")
    holding = [op for op in active_operations(project.id) if op in {"build", "tester"}]
    if holding:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Tester cannot start for {project.name} while "
                f"{', '.join(holding)} is running"
            ),
        )
    job_id = job_scheduler.submit(
        "run_tester", args=[project.id], project_id=project.id
    )
    return JobEnvelope(job_id=job_id, status="queued")
