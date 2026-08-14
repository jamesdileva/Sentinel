"""Build runner — discovers and executes build commands (docs/02 §3.5)."""

import datetime

from sqlmodel import Session

from app.core.logging import get_logger
from app.db.models import BuildLog, Project
from app.repositories import ProjectRepository
from app.services.command_runner import run_command
from app.utils.command_extractor import extract_build_commands

logger = get_logger(__name__)


class BuildRunner:
    """Executes the build command for a project and records a BuildLog."""

    def __init__(self, session: Session):
        self.session = session

    def discover_commands(self, project_path: str) -> dict[str, str]:
        """Detect install, startup, build, test, deploy commands."""
        return extract_build_commands(project_path)

    def run_build(
        self, project: Project, log: BuildLog | None = None, executor=run_command
    ) -> BuildLog:
        """Execute the project build command, capture output, return the log."""
        commands = project.stack.get("commands") if project.stack else None
        commands = commands or self.discover_commands(project.path)
        command = (commands or {}).get("build") or ""

        if log is None:
            log = BuildLog(project_id=project.id)
        log.commands = commands or {}
        self.session.add(log)
        self.session.commit()
        log = self.session.get(BuildLog, log.id)

        if not command:
            # v1.17.7.5: a project with no discoverable build command is
            # *not* a successful build — previously success=True/exit 0 made
            # the Builds page, the activity feed and job results claim a
            # pass. success stays None (nullable column) so callers can tell
            # "never actually built" from "built and passed/failed".
            log.success = None
            log.exit_code = None
            log.stdout = "No build command configured for this project."
            log.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.session.add(log)
            self.session.commit()
            logger.info("Build %s: no build command", log.id)
            return log

        result = executor(command, cwd=project.path)
        log.exit_code = result.exit_code
        log.success = result.exit_code == 0 and not result.timed_out
        log.stdout = result.stdout
        log.stderr = result.stderr
        if result.timed_out:
            log.stderr = (
                f"{result.stderr}\n[timed out after {result.duration_seconds}s]"
            )
        log.completed_at = datetime.datetime.now(datetime.timezone.utc)
        self.session.add(log)
        self.session.commit()
        logger.info(
            "Build %s for %s: exit_code=%s success=%s",
            log.id,
            project.name,
            log.exit_code,
            log.success,
        )
        return log

    @staticmethod
    def get_project(session: Session, project_id: str) -> Project:
        project = ProjectRepository(session).get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        return project
