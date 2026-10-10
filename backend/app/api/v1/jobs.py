"""Generic job endpoints — /api/v1/jobs (v1.17.19.11, audit B5).

One pollable lifecycle for every scheduler-submitted job, whatever domain
record its task also writes. Clients that used to infer state from result
history (tests, scans, testers) can read the row directly instead.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.connection import get_session
from app.repositories.job import JobRepository
from app.schemas import JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, session: Session = Depends(get_session)) -> JobRead:
    """Poll any submitted job: queued / running / succeeded / failed /
    cancelled, with its error text and domain pointer when finished."""
    job = JobRepository(session).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    return JobRead(
        id=job.id,
        type=job.type,
        project_id=job.project_id,
        status=job.status.value,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error,
        result_ref=job.result_ref,
    )
