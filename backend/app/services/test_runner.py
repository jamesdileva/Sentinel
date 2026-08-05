"""Test runner — executes and parses test suites (docs/02 §3.5)."""

import re
import time

from sqlmodel import Session

from app.core.logging import get_logger
from app.db.models import Project, TestResult
from app.repositories import ProjectRepository
from app.services.command_runner import run_command
from app.utils.command_extractor import extract_build_commands

logger = get_logger(__name__)


class TestRunner:
    """Executes the test command and parses framework output."""

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def parse_test_output(stdout: str, stderr: str) -> dict:
        """Parse pytest/jest/vitest summary lines into count dict."""
        text = f"{stdout}\n{stderr}"
        patterns: list[tuple[str, re.Pattern[str]]] = [
            ("passed", re.compile(r"(\d+)\s+passed", re.IGNORECASE)),
            ("failed", re.compile(r"(\d+)\s+failed", re.IGNORECASE)),
            ("errors", re.compile(r"(\d+)\s+error", re.IGNORECASE)),
            ("skipped", re.compile(r"(\d+)\s+skipped", re.IGNORECASE)),
        ]
        return {"passed": 0, "failed": 0, "errors": 0, "skipped": 0} | {
            key: int(match.group(1))
            for key, pattern in patterns
            if (match := pattern.search(text)) is not None
        }

    def discover_test_command(self, project_path: str) -> str:
        return extract_build_commands(project_path).get("test") or ""

    def run_tests(self, project: Project, executor=run_command) -> TestResult:
        """Execute the project test command and parse the output."""
        command = self.discover_test_command(project.path)
        framework = (
            "pytest"
            if command == "pytest"
            else ("jest" if "jest" in command else command or None)
        )
        started = time.monotonic()
        if not command:
            result = None
            counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        else:
            result = executor(command, cwd=project.path)
            counts = self.parse_test_output(result.stdout, result.stderr)

        duration = time.monotonic() - started
        summary = (
            f"{counts['passed']} passed, {counts['failed']} failed"
            if command
            else "No test command configured for this project."
        )
        test_result = TestResult(
            project_id=project.id,
            passed=counts["passed"],
            failed=counts["failed"],
            errors=counts["errors"],
            skipped=counts["skipped"],
            duration_seconds=round(duration, 3),
            framework=framework,
            summary=summary,
            raw_output=(result.stdout if result else "")[:4000]
            + ((result.stderr if result else "") or "")[:2000],
        )
        self.session.add(test_result)
        self.session.commit()
        logger.info("Tests for %s: %s (framework=%s)", project.name, summary, framework)
        return test_result

    @staticmethod
    def get_project(session: Session, project_id: str) -> Project:
        project = ProjectRepository(session).get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        return project
