"""Tester tasks — run a project's scripted tester in the job pool
(later.md Tier 2, docs/tier2_plan.md). Opens its own DB session like the
other pipeline tasks; the AppSession row carries the results."""

from sqlmodel import Session

from app.core.logging import get_logger
from app.db.connection import get_engine
from app.services import activity_bus
from app.services.build_runner import BuildRunner
from app.services.project_operations import (
    OperationBusyError,
    active_operations,
    project_operation,
)
from app.services.tester_runner import TesterRunner

logger = get_logger(__name__)


def run_tester_task(project_id: str) -> dict:
    """Execute the project's tester and record the resulting session.

    v1.17.19.10 (audit A7): testers drive the app's real UI, so a tester
    never runs alongside a build — the matrix refuses both directions. A
    duplicate tester (or one racing a build) fails the session with the
    blocking operations named, instead of clicking through a UI that a
    concurrent build is also driving.
    """
    logger.info("tester task starting for %s", project_id)
    with Session(get_engine()) as session:
        project = BuildRunner.get_project(session, project_id)
    try:
        with project_operation(project_id, "tester"):
            return _run_tester_task(project_id)
    except OperationBusyError as exc:
        logger.info("tester task refused for %s: %s", project_id, exc)
        with Session(get_engine()) as session:
            app_session = TesterRunner(session).record_busy(project, detail=str(exc))
        activity_bus.publish_event(
            "tester",
            f"Tester not started for {project.name}: busy",
            detail=str(exc),
            data={"project_id": project.id, "session_id": app_session.id},
        )
        return {
            "project_id": project.id,
            "session_id": app_session.id,
            "status": "skipped",
            "skipped": "operation-busy",
            "blocked_by": active_operations(project_id),
        }


def _run_tester_task(project_id: str) -> dict:
    with Session(get_engine()) as session:
        project = BuildRunner.get_project(session, project_id)
        app_session = TesterRunner(session).run(project)
        message = f"Tester {app_session.status} for {project.name}"
        detail = app_session.actual_outcome or ""
        activity_bus.publish_event(
            "tester",
            message,
            detail=detail[:200],
            data={
                "project_id": project.id,
                "session_id": app_session.id,
                "status": app_session.status,
            },
        )
        return {
            "project_id": project.id,
            "session_id": app_session.id,
            "status": app_session.status,
        }
