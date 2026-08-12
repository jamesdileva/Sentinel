#!/usr/bin/env python
"""Project Sentinel — the single starting point for the home server (Sprint 15).

Native install: no containers. The laptop (or any machine) clones the repo,
creates a venv, then `python run.py` starts the backend on 127.0.0.1:8000,
which also serves the built frontend from backend/app/static.

What run.py does (deterministic checks + start):
  1. Verifies Python and the backend venv.
  2. Ensures .env (copied from .env.example when missing) and data dirs.
  3. Startup checks: Ollama reachable, SQLite writable, frontend built.
  4. Launches uvicorn (with --reload for development).
  [service] mode: skip if the port is already serving (Task Scheduler rerun).
  [install|uninstall]: register/remove the "Sentinel" autostart task.

Usage:
    python run.py                 # checks + start on 127.0.0.1:8000
    python run.py --port 8080     # different port (also SENTINEL_PORT)
    python run.py --reload        # dev file-watch reload
    python run.py --check         # only run the startup checks
    python run.py --install       # register autostart (Task Scheduler)
    python run.py --uninstall     # remove the autostart task
    python run.py --service       # used by the autostart task itself
"""

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
DATA = ROOT / "data"
LOG_DIR = DATA / "logs"

PYTHON_MIN = (3, 11)

PYWIN = ROOT / ".venv" / "Scripts" / "pythonw.exe"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = ROOT / ".venv" / "bin" / "python3"
if not PYWIN.exists():
    PYWIN = PY


def _ok(msg: str) -> None:
    print(f"[ok]   {msg}")


def _warn(msg: str) -> None:
    print(f"[warn] {msg}")


def _fail(msg: str) -> None:
    print(f"[fail] {msg}")
    sys.exit(1)


def check_python() -> None:
    if sys.version_info < PYTHON_MIN:
        _fail(
            f"Python {'.'.join(map(str, PYTHON_MIN))}+ required (have {sys.version})."
        )


def ensure_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        example = ROOT / ".env.example"
        if example.exists():
            env_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            _warn(f"created {env_file.name} from {example.name} — review it")
        else:
            _warn(".env and .env.example both missing; using defaults")
    for sub in ("sqlite", "chroma", "logs", "world_sim"):
        (DATA / sub).mkdir(parents=True, exist_ok=True)


def clean_docker_tombstones() -> None:
    """Native install must never re-read docker-compose.yml files."""
    for candidate in (ROOT / "docker-compose.yml", ROOT / "docker-compose.dev.yml"):
        if candidate.exists():
            _warn(f"stale compose file present ({candidate.name}), ignoring it")


def port_taken(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def port_owner(port: int) -> str:
    """Best-effort PID of the process listening on a port (Windows netstat)."""
    if os.name != "nt":
        return ""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"], text=True, errors="ignore", timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and "LISTENING" in line and parts[1].endswith(f":{port}"):
            return parts[-1]
    return ""


def check_frontend() -> None:
    static_index = BACKEND / "app" / "static" / "index.html"
    if static_index.exists():
        _ok("frontend built (backend/app/static/index.html)")
    else:
        _warn(
            "frontend not built — chart and wallet pages will 404; "
            "run 'python scripts/build.py --dist' before serving"
        )


def check_sqlite() -> None:
    try:
        import sqlite3

        conn = sqlite3.connect(DATA / "sqlite" / "sentinel.db")
        conn.execute("select 1")
        conn.close()
        _ok("sqlite writable")
    except Exception as exc:  # noqa: BLE001
        _fail(f"sqlite check failed: {exc}")


def startup_checks() -> None:
    """Deterministic probes; never raises — failures are printed and exit 1."""
    check_python()
    ensure_env()
    clean_docker_tombstones()
    check_frontend()
    check_sqlite()
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    for status in run_python_checks():
        if status.ok:
            _ok(f"startup: {status.name} ({status.detail})")
        else:
            _warn(f"startup: {status.name} FAILED ({status.detail})")


def run_python_checks() -> list:
    from app.services.startup_check import run_startup_checks

    return run_startup_checks()


def start_server(args: argparse.Namespace) -> int:
    argv = [
        str(PY),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
    ]
    if args.reload:
        argv.append("--reload")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND) + os.pathsep + env.get("PYTHONPATH", "")
    print(f"[run] starting backend: {' '.join(argv)}")
    return subprocess.call(argv, cwd=BACKEND, env=env)


def install_mode(install: bool, uninstall: bool) -> int | None:
    if install or uninstall:
        arg = "--install" if install else "--uninstall"
        return subprocess.call(
            [str(PY), "scripts/install_service.py", arg, str(ROOT)], cwd=ROOT
        )
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run.py", description=__doc__)
    parser.add_argument(
        "--port", type=int, default=8000, help="listen port (default 8000)"
    )
    parser.add_argument("--check", action="store_true", help="run startup checks only")
    parser.add_argument(
        "--install", dest="install", action="store_true", help="register autostart task"
    )
    parser.add_argument(
        "--uninstall",
        dest="uninstall",
        action="store_true",
        help="remove autostart task",
    )
    parser.add_argument("--reload", action="store_true", help="dev auto-reload")
    parser.add_argument(
        "--service",
        action="store_true",
        help="autostart mode: skip if port already in use",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.install or args.uninstall:
        code = install_mode(args.install, args.uninstall)
        return 0 if code is None else code

    port = int(os.environ.get("SENTINEL_PORT", str(args.port)))

    if args.check:
        startup_checks()
        _ok("all startup checks done (no server started)")
        return 0

    if args.service and port_taken(port):
        _ok(f"port {port} already in use — server running, nothing to do")
        return 0

    if port_taken(port):
        pid = port_owner(port)
        pid_hint = f" (PID {pid})" if pid else ""
        _fail(
            f"port {port} is already in use{pid_hint} — another Sentinel is "
            "running.\n"
            f"       Usually a second console left open: close it (or "
            f"'taskkill /F /PID {pid or '<pid>'}'), or run with another "
            "port (--port)."
        )

    startup_checks()
    return start_server(args)


if __name__ == "__main__":
    sys.exit(main())
