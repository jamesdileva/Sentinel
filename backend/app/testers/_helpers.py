"""Shared tester context — deterministic steps for scripted testers
(later.md Tier 2, docs/tier2_plan.md).

Each helper writes a `[sentinel] checkpoint:` marker into the app's own log
(the session slice captures it, Rule 7 provenance). Every assertion is
deterministic: status codes, exit codes, substring/line matches — no AI
(Rule 3). Failures raise typed errors the runner maps to session statuses:
- TesterAssertionError -> failed (an expected value did not match)
- TesterEnvError -> investigate (launch failure, port bind, missing env)
- TesterTimeoutError -> investigate (a bounded wait expired)

Secrets rule: testers never carry credentials, and `cli()` never writes the
`env` values into the app log — only the command line and captured output.
"""

import time
from pathlib import Path

import httpx

from app.core.logging import get_logger
from app.services.app_sessions import _apps_dir, _slug
from app.services.build_runner import BuildRunner
from app.services.command_runner import run_command

logger = get_logger(__name__)

APP_LOG = "[sentinel] App launched"


class TesterAssertionError(Exception):
    """An expected value did not match — the tester is red."""


class TesterEnvError(Exception):
    """Environment problem (launch/port/binding) — needs investigation."""


class TesterTimeoutError(Exception):
    """A bounded wait expired — needs investigation."""


# pytest would try to collect these (names start with "Test"); opt out.
TesterAssertionError.__test__ = False
TesterEnvError.__test__ = False
TesterTimeoutError.__test__ = False


class TesterContext:
    """Handles handed to a tester's `run(ctx)`; one per session."""

    def __init__(self, project, session_id, service):
        self.project = project
        self.session_id = session_id
        self.service = service
        self.steps = 0
        self._offset = 0

    # ------------------------------------------------------------ recording

    def checkpoint(self, label: str) -> None:
        self.steps += 1
        self.service.checkpoint(self.session_id, label)

    def screenshot(self, label: str | None = None) -> None:
        checkpoint = self.service.checkpoint(
            self.session_id, label or f"screenshot {self.steps + 1}"
        )
        self.steps += 1
        self.service.capture(self.session_id, checkpoint.id)

    def screenshot_file(self, path: str, label: str | None = None) -> None:
        """Register a pre-rendered PNG (headless browser render) as a session
        screenshot — for browser-served apps whose UI has no window."""
        checkpoint = self.service.checkpoint(
            self.session_id, label or f"screenshot {self.steps + 1}"
        )
        self.steps += 1
        self.service.register_screenshot(self.session_id, path, checkpoint.id)

    def wait(self, seconds: float) -> None:
        time.sleep(seconds)

    # ------------------------------------------------------------------ log

    def _log_path(self) -> Path:
        return _apps_dir() / f"{_slug(self.project.name)}.log"

    def _append_log(self, line: str) -> None:
        self.service._append_log(self.project, line)

    def mark_log(self) -> None:
        """Remember the current log length; `new_log_lines()` returns only
        lines appended after this point (used to scope error scans to this
        run instead of the whole accumulated file)."""
        path = self._log_path()
        self._offset = path.stat().st_size if path.exists() else 0

    def new_log_lines(self) -> list[str]:
        path = self._log_path()
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as fh:
            fh.seek(self._offset)
            return fh.read().splitlines()

    def log_contains(self, pattern: str) -> bool:
        return any(pattern in line for line in self.new_log_lines())

    def wait_log(self, pattern: str, timeout_s: int = 60) -> None:
        """Poll the app log until a line contains `pattern` (substring)."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.log_contains(pattern):
                self.checkpoint(f"log matched: {pattern}")
                return
            time.sleep(1)
        raise TesterTimeoutError(
            f"Log pattern not seen within {timeout_s}s: {pattern!r}"
        )

    # ------------------------------------------------------------- app steps

    def launch(self, command: str, env: dict[str, str] | None = None) -> None:
        """Detached app launch into its own log (venv python rewriting and
        the `[sentinel] App launched` stamp come from build_runner)."""
        self.mark_log()
        launched, detail = BuildRunner._launch_app(self.project, command, env=env)
        if not launched:
            raise TesterEnvError(f"Launch failed: {detail}")
        self.checkpoint(f"launched: {command}")

    def http(
        self,
        method: str,
        url: str,
        expect: int = 200,
        expect_body: str | None = None,
        timeout_s: int = 20,
    ) -> None:
        try:
            response = httpx.request(method, url, timeout=timeout_s)
        except httpx.HTTPError as exc:
            raise TesterEnvError(f"HTTP {method} {url} unreachable: {exc}") from exc
        if response.status_code != expect:
            raise TesterAssertionError(
                f"HTTP {method} {url} -> {response.status_code}, expected {expect}"
            )
        if expect_body is not None and expect_body not in response.text:
            raise TesterAssertionError(
                f"HTTP {method} {url} body lacks {expect_body!r}"
            )
        self.checkpoint(f"http {method} {url} -> {response.status_code}")

    def cli(
        self,
        command: str,
        cwd: str | None = None,
        timeout_s: int = 120,
        expect_exit: int = 0,
        expect_stdout: str | None = None,
        expect_file: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """Foreground command; captured output is appended to the app log
        (provenance). `env` values are never written to the log."""
        result = run_command(
            command, cwd=cwd or self.project.path, timeout=timeout_s, env=env
        )
        self._append_log(f"[tester] $ {command}")
        if result.stdout:
            self._append_log(result.stdout.rstrip())
        if result.stderr:
            self._append_log(f"[stderr] {result.stderr.rstrip()}")
        if result.timed_out:
            raise TesterTimeoutError(f"CLI timed out after {timeout_s}s: {command}")
        if result.exit_code != expect_exit:
            raise TesterAssertionError(
                f"CLI exit {result.exit_code}, expected {expect_exit}: {command}"
            )
        if expect_stdout and expect_stdout not in (result.stdout + result.stderr):
            raise TesterAssertionError(f"CLI output lacks {expect_stdout!r}: {command}")
        if expect_file:
            path = Path(expect_file)
            if not path.is_absolute():
                path = Path(self.project.path) / path
            if not path.exists():
                raise TesterAssertionError(f"Expected file missing: {expect_file}")
        self.checkpoint(f"cli {command}")

    def pytest(
        self,
        command: str,
        cwd: str | None = None,
        timeout_s: int = 600,
        env: dict[str, str] | None = None,
    ) -> None:
        """Long-timeout CLI variant for the app's own test suite."""
        self.cli(command, cwd=cwd, timeout_s=timeout_s, expect_exit=0, env=env)


# pytest would try to collect these (names start with "Test"); opt out.
TesterAssertionError.__test__ = False
TesterEnvError.__test__ = False
TesterTimeoutError.__test__ = False
TesterContext.__test__ = False
