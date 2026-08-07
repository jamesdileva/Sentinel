#!/usr/bin/env python
"""Project Sentinel — development helper (docs/02 §5.2).

Starts/stops the Docker Compose stack in dev mode. Dev overrides live in
`docker-compose.dev.yml` and are loaded explicitly here; a bare
`docker compose up` on the laptop runs production (docs/02 §13.4).

Usage:
    python scripts/dev.py                # Start all services (dev mode)
    python scripts/dev.py --backend-only # Start only the backend (+ redis)
    python scripts/dev.py --frontend-only # Build/serve only the frontend
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
    cmd = [find_docker(), "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml"]
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
        help="Build and serve the production frontend container (port 8080)",
    )
    parser.add_argument(
        "--with-ollama", action="store_true", help="Include the Ollama AI profile"
    )
    parser.add_argument("--down", action="store_true", help="Stop all services")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = compose_command(args)
    print(f"$ {' '.join(command)}")
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
