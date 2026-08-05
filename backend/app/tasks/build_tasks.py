"""Pipeline tasks — build, test, and security scan (docs/02 §3.10).

Each task opens its own DB session (a worker is a separate process from the
API server) and persists results back to SQLite. Jobs are created by the API
before enqueueing; the task updates the pre-created row (job_id == task_id).
"""

from sqlmodel import Session

from app.core.logging import get_logger
from app.db.connection import get_engine
from app.db.models import BuildLog, Project
from app.services.build_runner import BuildRunner
from app.services.security_scanner import SecurityScanner
from app.services.test_runner import TestRunner
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


def _get_project(project_id: str) -> Project:
    with Session(get_engine()) as session:
        return BuildRunner.get_project(session, project_id)


@celery_app.task(name="app.tasks.build_tasks.run_build")
def run_build_task(project_id: str, log_id: str) -> dict:
    """Execute the build command for a project and update the BuildLog row."""
    logger.info("build task starting for %s", project_id)
    with Session(get_engine()) as session:
        project = BuildRunner.get_project(session, project_id)
        log = session.get(BuildLog, log_id)
        if log is None:
            log = BuildLog(id=log_id, project_id=project.id)
        log = BuildRunner(session).run_build(project, log=log)
        return {
            "job_id": log.id,
            "project_id": project.id,
            "success": log.success,
            "exit_code": log.exit_code,
        }


@celery_app.task(name="app.tasks.build_tasks.run_tests")
def run_tests_task(project_id: str) -> dict:
    """Execute the test command for a project and persist a TestResult."""
    logger.info("test task starting for %s", project_id)
    with Session(get_engine()) as session:
        project = TestRunner.get_project(session, project_id)
        result = TestRunner(session).run_tests(project)
        return {
            "job_id": result.id,
            "project_id": project.id,
            "passed": result.passed,
            "failed": result.failed,
            "summary": result.summary,
        }


@celery_app.task(name="app.tasks.build_tasks.run_security_scan")
def run_security_scan_task(project_id: str) -> dict:
    """Run all security scanners for a project and persist findings."""
    logger.info("scan task starting for %s", project_id)
    with Session(get_engine()) as session:
        project = SecurityScanner.get_project(session, project_id)
        findings = SecurityScanner(session).scan_project(project)
        return {"project_id": project.id, "count": len(findings)}


@celery_app.task(name="app.tasks.build_tasks.run_security_scan_all")
def run_security_scan_all() -> dict:
    """Scheduled beat task: scan every indexed project."""
    with Session(get_engine()) as session:
        from app.repositories import ProjectRepository

        projects = ProjectRepository(session).list(limit=1000)
    scanned = [run_security_scan_task(p.id) for p in projects]
    return {"projects_scanned": len(scanned)}
