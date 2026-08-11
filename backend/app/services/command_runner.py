"""Deterministic subprocess execution for build/test/scan runners.

Runners never shell out through `os.system`; they always go through
`run_command`, which bounds execution time and captures stdout/stderr.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings

_GIT_CANDIDATES = (
    r"C:\Program Files\Git\cmd",
    r"C:\Program Files (x86)\Git\cmd",
    r"%LOCALAPPDATA%\Programs\Git\cmd",
)


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


def resolve_git() -> str | None:
    """Locate a usable `git` executable (full path), or None.

    Tries, in order: `SENTINEL_GIT_EXECUTABLE`, `shutil.which("git")` (PATH),
    then the standard Git-for-Windows install directories. Needed because the
    Task Scheduler autostart task (pythonw) runs with a minimal PATH where
    `git` is not resolvable (v1.17.3).
    """
    override = settings.git_executable
    if override:
        if Path(override).is_file():
            return str(Path(override))
        return override
    found = shutil.which("git")
    if found:
        return found
    for candidate in _GIT_CANDIDATES:
        expanded = Path(os.path.expandvars(candidate))
        exe = expanded / "git.exe"
        if exe.is_file():
            return str(exe)
    return None


def git_command() -> str:
    """The git binary to embed in commands (resolved once per call)."""
    resolved = resolve_git()
    if not resolved:
        raise FileNotFoundError(
            "git not found — install Git for Windows or set "
            "SENTINEL_GIT_EXECUTABLE in .env"
        )
    return resolved


def run_command(
    command: str,
    cwd: str | Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run a command, capture output, and return a structured result."""
    timeout = timeout if timeout is not None else settings.command_timeout_seconds
    # v1.17.3: a partial `env` must overlay the inherited environment, not
    # replace it — subprocess.run() with env={} drops PATH, which made every
    # `git` invocation fail with "'git' is not recognized".
    full_env = {**os.environ, **(env or {})}
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
            env=full_env,
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
