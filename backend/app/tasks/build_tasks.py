"""Pipeline tasks — build, test, and security scan (docs/02 §3.10).

Each task opens its own DB session (jobs run in the in-process scheduler's
worker threads, separate from the request coroutine) and persists results
back to SQLite. Jobs are created by the API before enqueueing; the task
updates the pre-created row (job_id == submitted task id).
"""

from sqlmodel import Session

from app.core.logging import get_logger
from app.db.connection import get_engine
from app.db.models import BuildLog, Project
from app.services import activity_bus
from app.services.build_runner import BuildRunner
from app.services.security_scanner import SecurityScanner
from app.services.test_runner import TestRunner

logger = get_logger(__name__)


def _get_project(project_id: str) -> Project:
    with Session(get_engine()) as session:
        return BuildRunner.get_project(session, project_id)


def run_build_task(project_id: str, log_id: str) -> dict:
    """Execute the build command for a project and update the BuildLog row."""
    logger.info("build task starting for %s", project_id)
    with Session(get_engine()) as session:
        project = BuildRunner.get_project(session, project_id)
        log = session.get(BuildLog, log_id)
        if log is None:
            log = BuildLog(id=log_id, project_id=project.id)
        log = BuildRunner(session).run_build(project, log=log)
        if log.success is None:
            message = f"Build skipped for {project.name} — no build command"
            detail = "no command configured"
        elif log.success:
            message = f"Build passed for {project.name}"
            detail = f"exit code {log.exit_code}"
        else:
            message = f"Build failed for {project.name}"
            detail = f"exit code {log.exit_code}"
        activity_bus.publish_event(
            "build",
            message,
            detail=detail,
            data={"project_id": project.id, "success": bool(log.success)},
        )
        return {
            "job_id": log.id,
            "project_id": project.id,
            "success": log.success,
            "exit_code": log.exit_code,
        }


def run_tests_task(project_id: str) -> dict:
    """Execute the test command for a project and persist a TestResult."""
    logger.info("test task starting for %s", project_id)
    with Session(get_engine()) as session:
        project = TestRunner.get_project(session, project_id)
        result = TestRunner(session).run_tests(project)
        errors = getattr(result, "errors", 0)
        outcome = "passed" if result.failed == 0 and errors == 0 else "failed"
        activity_bus.publish_event(
            "test",
            f"Tests {outcome} for {project.name}",
            detail=(
                f"{result.passed} passed, {result.failed} failed, " f"{errors} errors"
            ),
            data={
                "project_id": project.id,
                "passed": result.passed,
                "failed": result.failed,
            },
        )
        return {
            "job_id": result.id,
            "project_id": project.id,
            "passed": result.passed,
            "failed": result.failed,
            "summary": result.summary,
        }


def run_security_scan_task(project_id: str) -> dict:
    """Run all security scanners for a project and persist findings."""
    logger.info("scan task starting for %s", project_id)
    with Session(get_engine()) as session:
        project = SecurityScanner.get_project(session, project_id)
        findings = SecurityScanner(session).scan_project(project)
        activity_bus.publish_event(
            "security",
            f"Security scan of {project.name} found {len(findings)} finding(s)",
            data={"project_id": project.id, "count": len(findings)},
        )
        return {"project_id": project.id, "count": len(findings)}


def run_security_scan_all() -> dict:
    """Scan every indexed project (v1.17.6.6: the daily scan runs as the
    final step of the repo-sync pass — sync -> index(if needed) -> scan —
    instead of a separate hourly beat; the manual Security-page scan is
    unchanged)."""
    with Session(get_engine()) as session:
        from app.repositories import ProjectRepository

        projects = ProjectRepository(session).list(limit=1000)
    scanned = [run_security_scan_task(p.id) for p in projects]
    return {"projects_scanned": len(scanned)}
