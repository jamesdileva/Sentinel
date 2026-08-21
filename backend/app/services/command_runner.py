"""Deterministic subprocess execution for build/test/scan runners.

Runners never shell out through `os.system`; they always go through
`run_command`, which bounds execution time and captures stdout/stderr.
"""

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

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


def _kill_tree(pid: int) -> None:
    """Audit A4 (v1.17.18.1): kill a process tree on Windows.

    Uses `taskkill /T /F /PID` to reap the child and all its grandchildren
    (npm, python, node trees that `shell=True` spawns).  Best-effort — a
    missing PID or access error is logged and swallowed.
    """
    try:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True,
            timeout=5,
        )
    except Exception:  # noqa: BLE001 — best-effort cleanup
        logger.debug("taskkill tree for PID %d failed", pid, exc_info=True)


def run_command(
    command: str,
    cwd: str | Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run a command, capture output, and return a structured result.

    v1.17.18.1 (audit A4): uses Popen with CREATE_NEW_PROCESS_GROUP so that
    a timeout kills the entire child tree (taskkill /T) — not just the
    direct cmd.exe, which left grandchildren (npm, python, node) orphaned.
    """
    timeout = timeout if timeout is not None else settings.command_timeout_seconds
    full_env = {**os.environ, **(env or {})}
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=flags,
            env=full_env,
        )
    except OSError as exc:
        return CommandResult(
            command=command,
            exit_code=-1,
            stdout="",
            stderr=str(exc),
            duration_seconds=0.0,
        )
    started = time.monotonic()
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return CommandResult(
            command=command,
            exit_code=proc.returncode,
            stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
            stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
            # v1.17.18.4 (audit2 S5): report the MEASURED duration — the
            # old code reported the timeout ceiling on the success path too.
            duration_seconds=round(time.monotonic() - started, 3),
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "Command timed out after %ds: %s — killing process tree", timeout, command
        )
        _kill_tree(proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            # v1.17.18.4 (audit2 S5): a stubborn child that ignores
            # taskkill /T /F must not escape run_command's contract of
            # always returning a structured result.
            logger.warning("Post-kill drain timed out for: %s", command)
            stdout, stderr = b"", b""
        return CommandResult(
            command=command,
            exit_code=-1,
            stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
            stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
            duration_seconds=round(time.monotonic() - started, 3),
            timed_out=True,
        )
    except OSError as exc:
        return CommandResult(
            command=command,
            exit_code=-1,
            stdout="",
            stderr=str(exc),
            duration_seconds=round(time.monotonic() - started, 3),
        )
