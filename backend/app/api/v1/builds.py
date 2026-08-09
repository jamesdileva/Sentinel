"""Build endpoints — /api/v1/builds.

Run a build as an async job on the in-process scheduler (docs/02 §5.3). The
job row is created here with id == the submitted job id, so GET /status/{job_id}
is a plain DB read.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.connection import get_session
from app.db.models import BuildLog
from app.repositories import BuildLogRepository, ProjectRepository
from app.schemas import BuildLogRead, BuildTrigger, JobStatus, build_status_from_log
from app.services.job_scheduler import scheduler as job_scheduler

router = APIRouter(prefix="/builds", tags=["builds"])


def _project_or_404(project_id: str, session: Session) -> object:
    project = ProjectRepository(session).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}")
    return project


@router.post("/run", status_code=202, response_model=JobStatus)
def run_build(
    payload: BuildTrigger, session: Session = Depends(get_session)
) -> JobStatus:
    """Enqueue a build for a project and return a pollable job status."""
    project = _project_or_404(payload.project_id, session)
    job_id = str(uuid.uuid4())
    session.add(BuildLog(id=job_id, project_id=project.id))
    session.commit()
    job_scheduler.submit("run_build", args=[project.id, job_id], task_id=job_id)
    session.expire_all()
    return build_status_from_log(session.get(BuildLog, job_id))


@router.get("/status/{job_id}", response_model=JobStatus)
def get_build_status(job_id: str, session: Session = Depends(get_session)) -> JobStatus:
    """Poll a build job."""
    log = session.get(BuildLog, job_id)
    if log is None:
        raise HTTPException(status_code=404, detail=f"Unknown build job: {job_id}")
    return build_status_from_log(log)


@router.get("/history", response_model=list[BuildLogRead])
def list_builds(
    project_id: str, session: Session = Depends(get_session)
) -> list[object]:
    """Most recent builds for a project."""
    _project_or_404(project_id, session)
    return BuildLogRepository(session).get_by_project(project_id)
