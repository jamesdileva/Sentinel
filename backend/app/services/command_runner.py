"""Deterministic subprocess execution for build/test/scan runners.

Runners never shell out through `os.system`; they always go through
`run_command`, which bounds execution time and captures stdout/stderr.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


def run_command(
    command: str,
    cwd: str | Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run a command, capture output, and return a structured result."""
    timeout = timeout if timeout is not None else settings.command_timeout_seconds
    try:
        start = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        return CommandResult(
            command=command,
            exit_code=start.returncode,
            stdout=start.stdout,
            stderr=start.stderr,
            duration_seconds=0.0,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            exit_code=-1,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            duration_seconds=float(timeout),
            timed_out=True,
        )
    except OSError as exc:
        return CommandResult(
            command=command,
            exit_code=-1,
            stdout="",
            stderr=str(exc),
            duration_seconds=0.0,
        )
