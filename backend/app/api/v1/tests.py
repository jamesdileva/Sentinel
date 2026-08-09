"""Test run endpoints — /api/v1/tests.

Run a test suite as an in-process scheduler job; results are read via
GET /results (docs/02 §5.4). Result rows have no running/queued state, so
polling uses the results list itself.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.connection import get_session
from app.repositories import ProjectRepository, TestRepository
from app.schemas import TestResultRead
from app.schemas.test import TestRunResponse
from app.services.job_scheduler import scheduler as job_scheduler

router = APIRouter(prefix="/tests", tags=["tests"])


def _project_or_404(project_id: str, session: Session) -> object:
    project = ProjectRepository(session).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}")
    return project


@router.post("/run", status_code=202, response_model=TestRunResponse)
def run_tests(
    project_id: str, session: Session = Depends(get_session)
) -> TestRunResponse:
    """Enqueue a test run for a project."""
    project = _project_or_404(project_id, session)
    job_id = job_scheduler.submit("run_tests", args=[project.id])
    return TestRunResponse(job_id=job_id, status="queued")


@router.get("/results", response_model=list[TestResultRead])
def list_test_results(
    project_id: str, session: Session = Depends(get_session)
) -> list[object]:
    """Most recent test results for a project."""
    _project_or_404(project_id, session)
    return TestRepository(session).get_by_project(project_id)
