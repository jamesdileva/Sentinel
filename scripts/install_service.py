#!/usr/bin/env python
"""Project Sentinel — Windows Task Scheduler autostart (Sprint 15).

Registers the "Sentinel" task so the always-on laptop runs the server from
login: every 5 minutes `run.py --service` runs, which exits immediately if
the port is already serving. Runs the repo's own venv (pythonw, no console
window); paths are derived at runtime so the same script works for any
checkout location.

Usage:
    python scripts/install_service.py --install [REPO_ROOT]
    python scripts/install_service.py --uninstall
"""

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "Sentinel"
INTERVAL_MINUTES = 5


def locate_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def task_command(repo: Path) -> str:
    """Full command line Task Scheduler stores (single string)."""
    pythonw = repo / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        pythonw = repo / ".venv" / "Scripts" / "python.exe"
    run_script = repo / "run.py"
    return f'"{pythonw}" "{run_script}" --service'


def schtasks(argv: list[str]) -> int:
    return subprocess.call(["schtasks", *argv])


def install(repo: Path, interval: int) -> int:
    return schtasks(
        [
            "/create",
            "/tn",
            TASK_NAME,
            "/tr",
            task_command(repo),
            "/sc",
            "MINUTE",
            "/mo",
            str(interval),
            "/f",
        ]
    )


def uninstall() -> int:
    return schtasks(["/delete", "/tn", TASK_NAME, "/f"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="install_service.py", description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true", help="register autostart task")
    group.add_argument("--uninstall", action="store_true", help="remove autostart task")
    parser.add_argument(
        "repo",
        nargs="?",
        type=Path,
        default=None,
        help="repo root (defaults to this script's parent parent)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = (args.repo or locate_repo_root()).resolve()

    if args.install:
        if not (repo / "run.py").exists():
            sys.exit(f"run.py not found in {repo} — pass the repo root as an argument")
        print(f"[task] registering {TASK_NAME}: {task_command(repo)}")
        return install(repo, INTERVAL_MINUTES)
    print(f"[task] removing {TASK_NAME}")
    return uninstall()


if __name__ == "__main__":
    sys.exit(main())
