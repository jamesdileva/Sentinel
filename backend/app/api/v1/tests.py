"""Test run endpoints — /api/v1/tests.

Run a test suite as an in-process scheduler job; results are read via
GET /results (docs/02 §5.4). Result rows have no running/queued state, so
polling uses the results list itself.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.v1._deps import project_or_404
from app.db.connection import get_session
from app.repositories import TestRepository
from app.schemas import TestResultRead
from app.schemas.test import TestRunResponse
from app.services.job_scheduler import scheduler as job_scheduler
from app.services.project_operations import active_operations

router = APIRouter(prefix="/tests", tags=["tests"])


@router.post("/run", status_code=202, response_model=TestRunResponse)
def run_tests(
    project_id: str, session: Session = Depends(get_session)
) -> TestRunResponse:
    """Enqueue a test run for a project.

    v1.17.19.10 (audit A7): a second suite against the same tree only wastes
    the pool, so a duplicate is refused with 409 rather than queued. Security
    scans and knowledge indexing are deliberately *not* blocked — the audit's
    matrix keeps them free to run alongside tests.
    """
    project = project_or_404(project_id, session)
    if "test" in active_operations(project.id):
        raise HTTPException(
            status_code=409,
            detail=f"Tests cannot start for {project.name} while a test is running",
        )
    job_id = job_scheduler.submit("run_tests", args=[project.id], project_id=project.id)
    return TestRunResponse(job_id=job_id, status="queued")


@router.get("/results", response_model=list[TestResultRead])
def list_test_results(
    project_id: str, session: Session = Depends(get_session)
) -> list[object]:
    """Most recent test results for a project."""
    project_or_404(project_id, session)
    return TestRepository(session).get_by_project(project_id)
