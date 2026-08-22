"""Build runner — discovers and executes build commands (docs/02 §3.5).

v1.17.8.0 build->open: after a successful build (or when no build step is
needed) the project's startup command is launched detached, so a build run
both compiles *and* opens the app — the dev-machine workflow, not a fresh-PC
test. The launch is always user-initiated (the Run Build click); beats never
launch anything (Rule 2).
v1.17.13.4: browser-served apps actually open. The project's tester declares
`web_url` / `extra_launch` / `ports` (app.testers.Tester); before launching,
listeners on the declared ports are killed (restart semantics — the open
instance is the current code, no drift orphans), the stored startup plus
each extra server is launched detached, and the default browser opens the
web_url. Desktop apps (no web_url) are unchanged.
"""

import datetime
import os
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
from app.utils.window_capture import _process_exe_path

logger = get_logger(__name__)


def _slug(name: str) -> str:
    return re.sub(r"[^\w.-]+", "-", name.strip()) or "project"


def _pid_owned_by_project(pid: str, project_root: str) -> bool:
    """True when the PID's executable lives under the project root (audit2 S8).
    Unresolvable PIDs are treated as not-owned — the kill is skipped and
    logged, never guessed."""
    exe = _process_exe_path(int(pid))
    if exe is None:
        return False
    root = os.path.normpath(project_root).casefold()
    exe_norm = os.path.normpath(exe).casefold()
    return exe_norm == root or exe_norm.startswith(root + os.sep)


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
        # v1.17.13.4: the project's tester carries the app facts build->open
        # needs (web_url, extra servers, ports) — None for projects without
        # a custom tester (desktop apps open their own window). Local import:
        # app.testers._helpers imports BuildRunner at module level.
        from app.testers import TESTERS  # noqa: PLC0415

        facts = TESTERS.get(_slug(project.name))

        if log is None:
            log = BuildLog(project_id=project.id)
        log.commands = commands or {}
        self.session.add(log)
        self.session.commit()
        log = self.session.get(BuildLog, log.id)

        if not command:
            self._finish_without_build(log, project, startup, facts)
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
            self._launch_into_log(log, project, startup, facts)
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
        self, log: BuildLog, project: Project, startup: str, facts=None
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
        self._launch_into_log(log, project, startup, facts)
        self.session.add(log)
        self.session.commit()

    def _launch_into_log(
        self, log: BuildLog, project: Project, startup: str, facts=None
    ) -> None:
        """Launch the startup command + the tester's extra servers detached,
        then open the browser at the tester's web_url (v1.17.13.4)."""
        ports = tuple(facts.ports) if facts else ()
        if ports:
            killed = self._free_ports(ports, project_root=project.path)
            log.stdout = (
                f"{log.stdout or ''}\nFreed ports for restart: "
                f"{', '.join(map(str, killed)) if killed else 'none listening'}"
            )
        details = []
        for cmd in (startup, *((facts.extra_launch) if facts else ())):
            if not cmd:
                continue
            launched, detail = self._launch_app(project, cmd)
            if launched:
                details.append(detail)
                log.stdout = f"{log.stdout or ''}\nApp launched: {detail}"
            else:
                log.stdout = f"{log.stdout or ''}\nApp launch failed: {detail}"
        web_url = facts.web_url if facts else None
        if web_url and details:
            if self._open_browser(web_url):
                log.stdout = f"{log.stdout or ''}\nApp opened: {web_url}"
            else:
                log.stdout = f"{log.stdout or ''}\nApp open failed: {web_url}"
        log.launch_command = details[0] if details else None

    @staticmethod
    def _launch_app(
        project: Project, startup_command: str, env: dict[str, str] | None = None
    ) -> tuple[bool, str]:
        """Detached launch of the app through the repo's own venv python.

        Returns (launched, detail) where detail is the resolved command or
        the failure reason. The child outlives the request (no timeout) and
        appends to data/logs/apps/<slug>.log. `env` (v1.17.11: tester
        launches) overlays the inherited environment — never replaces it.
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
            # v1.17.11.0: a command that already names the venv interpreter
            # with `-m uvicorn` (tester launches) must not be rewritten a
            # second time — the old unconditional regex produced
            # `"<venv>\python.exe" -m "<venv>\python.exe" -m uvicorn …`,
            # which died with ModuleNotFoundError before binding the port.
            if f'"{python}" -m uvicorn' not in command:
                command = re.sub(
                    r"(^|\s)uvicorn(?=\s)",
                    lambda m: m.group(1) + f'"{python}" -m uvicorn',
                    command,
                )
        apps_dir = Path(settings.db_path).parent.parent / "logs" / "apps"
        apps_dir.mkdir(parents=True, exist_ok=True)
        # Audit A2 (v1.17.18.1): rotate the previous run's log before opening,
        # so accumulation across launches stays bounded.
        from app.services.app_sessions import _rotate_app_log

        _rotate_app_log(_slug(project.name))
        log_file = open(apps_dir / f"{_slug(project.name)}.log", "a", encoding="utf-8")
        # v1.17.8.2: CREATE_NEW_PROCESS_GROUP only — DETACHED_PROCESS makes
        # cmd.exe spawn external children (npm, python, node) with invalid
        # stdout/stderr handles, so the whole app tree's output silently
        # vanished from the log (probed: direct children were fine, every
        # cmd-spawned child lost its output even on natural exit). With the
        # group flag alone the child tree inherits the file handle and every
        # line lands in <slug>.log; the app attaches to Sentinel's (hidden)
        # console, which is harmless.
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            subprocess.Popen(
                command,
                shell=True,
                cwd=str(root),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=flags,
                env={**os.environ, **(env or {})},
            )
            # v1.17.8.0: the child's own stdout/stderr may be block-buffered
            # (and a crash or concurrent-kill drops the unflushed tail), so the
            # parent stamps the launch into the log first — the marker always
            # lands, the child's lines follow when its buffers flush.
            log_file.write(
                "[sentinel] App launched "
                f"{datetime.datetime.now().isoformat(timespec='seconds')}: {command}\n"
            )
            log_file.flush()
            log_file.close()
            return True, command
        except OSError as exc:
            log_file.close()
            return False, str(exc)

    @staticmethod
    def _free_ports(
        ports: tuple[int, ...], project_root: str | None = None
    ) -> list[int]:
        """Kill every listener on the app's ports so the fresh launch binds
        them (v1.17.13.4 restart semantics — build->open means the current
        code, not an orphan instance that drifted to another port).
        Windows: `netstat -ano` to find the PIDs, `taskkill /F` to stop
        them. Returns the PIDs actually killed (empty on no listeners or
        tool failure — a busy port then simply makes the app bind another).

        v1.17.18.6 (audit2 S8): with a project_root, a listener is only
        killed when its executable actually lives under that directory —
        an unrelated process that happens to hold the port (another
        project's dev server, anything else) is reported and left alone."""
        if not ports:
            return []
        try:
            out = (
                subprocess.run(
                    ["netstat", "-ano"], capture_output=True, text=True, timeout=15
                ).stdout
                or ""
            )
        except (OSError, subprocess.SubprocessError):
            return []
        listeners = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == "TCP" and parts[3] == "LISTENING":
                local = parts[1].rsplit(":", 1)
                if len(local) == 2 and local[1].isdigit():
                    if int(local[1]) in ports and parts[4].isdigit():
                        listeners[int(local[1])] = parts[4]
        killed = []
        for pid in sorted({p for p in listeners.values()}):
            if project_root is not None and not _pid_owned_by_project(
                pid, project_root
            ):
                logger.warning(
                    "Refusing to free port held by PID %s — its executable is "
                    "not under %s (not this project's server)",
                    pid,
                    project_root,
                )
                continue
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    capture_output=True,
                    timeout=15,
                )
                killed.append(int(pid))
            except (OSError, subprocess.SubprocessError):
                continue
        return killed

    @staticmethod
    def _open_browser(url: str) -> bool:
        """Open `url` in the user's default browser (Windows startfile —
        no shell, no window of ours). Never called for desktop apps."""
        try:
            os.startfile(url)
            return True
        except (OSError, AttributeError):
            return False

    @staticmethod
    def get_project(session: Session, project_id: str) -> Project:
        project = ProjectRepository(session).get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        return project
