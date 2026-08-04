#!/usr/bin/env python
"""Project Sentinel — development helper (docs/02 §5.2).

Starts/stops the Docker Compose stack. On Windows the Docker CLI may not be on
PATH in every shell, so the Docker Desktop install location is probed as well.

Usage:
    python scripts/dev.py                # Start all services (dev mode)
    python scripts/dev.py --backend-only # Start only the backend (+ redis)
    python scripts/dev.py --frontend-only # Start only the frontend (Sprint 5+)
    python scripts/dev.py --with-ollama  # Also start the Ollama AI backend
    python scripts/dev.py --down         # Stop all services
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_DOCKER_DESKTOP_CLI = Path(
    r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
)


def find_docker() -> str:
    """Locate the Docker CLI, preferring PATH and falling back to Docker Desktop."""
    found = shutil.which("docker")
    if found:
        return found
    if _DOCKER_DESKTOP_CLI.exists():
        return str(_DOCKER_DESKTOP_CLI)
    sys.exit("Docker CLI not found. Install Docker Desktop and try again.")


def compose_command(args: argparse.Namespace) -> list[str]:
    """Build the docker compose argv for the given flags (pure, testable)."""
    cmd = [find_docker(), "compose"]
    if args.with_ollama:
        cmd.extend(["--profile", "ollama"])
    if args.down:
        return [*cmd, "down"]
    cmd.extend(["up", "-d", "--build"])
    if args.backend_only:
        cmd.append("backend")
    elif args.frontend_only:
        cmd.append("frontend")
    return cmd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--backend-only", action="store_true", help="Backend + redis only")
    mode.add_argument(
        "--frontend-only",
        action="store_true",
        help="Frontend only (not available until Sprint 5)",
    )
    parser.add_argument(
        "--with-ollama", action="store_true", help="Include the Ollama AI profile"
    )
    parser.add_argument("--down", action="store_true", help="Stop all services")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.frontend_only:
        print("Frontend is not built yet (Sprint 5). Starting backend instead.")
        args.backend_only = True
        args.frontend_only = False

    command = compose_command(args)
    print(f"$ {' '.join(command)}")
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
