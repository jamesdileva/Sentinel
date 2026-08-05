"""Test run endpoints — /api/v1/tests.

Trigger test runs as async Celery jobs; results are read via GET /results
(docs/02 §5.4). Result rows have no running/queued state, so polling uses the
results list itself.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.connection import get_session
from app.repositories import ProjectRepository, TestRepository
from app.schemas import TestResultRead
from app.schemas.test import TestRunResponse
from app.tasks.build_tasks import run_tests_task

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
    task = run_tests_task.delay(project.id)
    return TestRunResponse(job_id=task.id, status="queued")


@router.get("/results", response_model=list[TestResultRead])
def list_test_results(
    project_id: str, session: Session = Depends(get_session)
) -> list[object]:
    """Most recent test results for a project."""
    _project_or_404(project_id, session)
    return TestRepository(session).get_by_project(project_id)
