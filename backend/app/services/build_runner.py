"""Build runner — discovers and executes build commands (docs/02 §3.5).

v1.17.8.0 build->open: after a successful build (or when no build step is
needed) the project's startup command is launched detached, so a build run
both compiles *and* opens the app — the dev-machine workflow, not a fresh-PC
test. The launch is always user-initiated (the Run Build click); beats never
launch anything (Rule 2).
"""

import datetime
import re
import subprocess
from pathlib import Path

from sqlmodel import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import BuildLog, Project
from app.repositories import ProjectRepository
from app.services.command_runner import run_command
from app.utils.command_extractor import extract_build_commands, project_venv_python

logger = get_logger(__name__)


def _slug(name: str) -> str:
    return re.sub(r"[^\w.-]+", "-", name.strip()) or "project"


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
        """Execute the project build command, capture output, return the log.

        v1.17.8.0: after a successful build — or instead of a build when the
        project has no compile step — the startup command is launched
        detached (the app stays open; no command timeout applies to it).
        """
        commands = project.stack.get("commands") if project.stack else None
        if not (commands or {}).get("build") and not (commands or {}).get("startup"):
            # v1.17.7.6: the index-time stack may predate the current
            # extractor set (e.g. a C++/CMake repo indexed before CMake
            # discovery existed) — re-discover rather than declare a skip.
            # v1.17.8.0: only when *both* build and startup are missing, so a
            # stored startup is never discarded by re-discovery.
            commands = self.discover_commands(project.path)
        command = (commands or {}).get("build") or ""
        startup = (commands or {}).get("startup") or ""

        if log is None:
            log = BuildLog(project_id=project.id)
        log.commands = commands or {}
        self.session.add(log)
        self.session.commit()
        log = self.session.get(BuildLog, log.id)

        if not command:
            self._finish_without_build(log, project, startup)
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
        if log.success and startup:
            self._launch_into_log(log, project, startup)
        log.completed_at = datetime.datetime.now(datetime.timezone.utc)
        self.session.add(log)
        self.session.commit()
        logger.info(
            "Build %s for %s: exit_code=%s success=%s launch=%s",
            log.id,
            project.name,
            log.exit_code,
            log.success,
            log.launch_command or "-",
        )
        return log

    def _finish_without_build(
        self, log: BuildLog, project: Project, startup: str
    ) -> None:
        """v1.17.7.5 semantics, extended for build->open: with no compile
        step the run is a success *only* when an app was actually launched;
        a project with neither build nor startup stays the honest
        success=None "no build command" record."""
        log.completed_at = datetime.datetime.now(datetime.timezone.utc)
        if not startup:
            log.success = None
            log.exit_code = None
            log.stdout = "No build command configured for this project."
            self.session.add(log)
            self.session.commit()
            logger.info("Build %s: no build command", log.id)
            return
        log.success = True
        log.exit_code = None
        log.stdout = "Build not needed — this project has no compile step."
        self._launch_into_log(log, project, startup)
        self.session.add(log)
        self.session.commit()

    def _launch_into_log(self, log: BuildLog, project: Project, startup: str) -> None:
        """Launch the startup command detached and record the outcome."""
        launched, detail = self._launch_app(project, startup)
        if launched:
            log.launch_command = detail
            log.stdout = f"{log.stdout or ''}\nApp launched: {detail}"
        else:
            log.stdout = f"{log.stdout or ''}\nApp launch failed: {detail}"

    @staticmethod
    def _launch_app(project: Project, startup_command: str) -> tuple[bool, str]:
        """Detached launch of the app through the repo's own venv python.

        Returns (launched, detail) where detail is the resolved command or
        the failure reason. The child outlives the request (no timeout) and
        appends to data/logs/apps/<slug>.log.
        """
        root = Path(project.path)
        python = project_venv_python(root)
        command = startup_command
        if python:
            # lambda, not a backreference string: the venv path (C:\Users\...)
            # contains backslashes that re.sub would try to escape.
            # v1.17.8.0: venv console-script binaries (pytest, uvicorn) live
            # in the venv's Scripts dir, not on the global PATH — rewrite
            # them to the venv interpreter's `-m` form, same as pytest.
            command = re.sub(
                r"(^|\s)python(?=\s)",
                lambda m: m.group(1) + f'"{python}"',
                command,
            )
            command = re.sub(
                r"(^|\s)uvicorn(?=\s)",
                lambda m: m.group(1) + f'"{python}" -m uvicorn',
                command,
            )
        apps_dir = Path(settings.db_path).parent.parent / "logs" / "apps"
        apps_dir.mkdir(parents=True, exist_ok=True)
        log_file = open(apps_dir / f"{_slug(project.name)}.log", "a", encoding="utf-8")
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        try:
            subprocess.Popen(
                command,
                shell=True,
                cwd=str(root),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
            return True, command
        except OSError as exc:
            log_file.close()
            return False, str(exc)

    @staticmethod
    def get_project(session: Session, project_id: str) -> Project:
        project = ProjectRepository(session).get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        return project
