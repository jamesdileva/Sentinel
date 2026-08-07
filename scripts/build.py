#!/usr/bin/env python
"""Project Sentinel — build helper (Sprint 12, docs/02 §12.6).

Deterministic build of the deployable artifacts the home server needs:
  1. Backend Docker image (backend + redis + worker).
  2. Frontend Docker image (multi-stage node build → nginx).
  3. Verified with the project's own test suites before and after packaging.

Usage:
    python scripts/build.py            # Build both images (default)
    python scripts/build.py --backend  # Build only the backend image
    python scripts/build.py --frontend # Build only the frontend image
    python scripts/build.py --test     # Run test suites, build nothing
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BACKEND_IMAGE = "sentinel-backend:latest"
FRONTEND_IMAGE = "sentinel-frontend:latest"

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


def run(argv: list[str], cwd: Path = ROOT) -> int:
    print(f"$ {' '.join(argv)}")
    return subprocess.run(argv, cwd=cwd).returncode


def run_backend_tests() -> int:
    bpython = Path("backend") / ".venv" / "Scripts" / "python.exe"
    if not bpython.exists():
        bpython = Path("backend") / ".venv" / "bin" / "python3"
    return run(
        [str(bpython), "-m", "pytest", "tests", "--quiet"],
        cwd=ROOT / "backend",
    )


def run_frontend_tests() -> int:
    return run(["npm", "run", "test"], cwd=ROOT / "frontend")


def build_backend() -> int:
    docker = find_docker()
    return run(
        [
            docker,
            "build",
            "-t",
            BACKEND_IMAGE,
            "-f",
            "docker/backend/Dockerfile",
            ".",
        ]
    )


def build_frontend() -> int:
    docker = find_docker()
    return run(
        [
            docker,
            "build",
            "-t",
            FRONTEND_IMAGE,
            "-f",
            "docker/frontend/Dockerfile",
            ".",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build.py", description=__doc__)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--backend", action="store_true", help="Backend image only")
    target.add_argument("--frontend", action="store_true", help="Frontend image only")
    parser.add_argument(
        "--test",
        dest="test_only",
        action="store_true",
        help="Run test suites and skip image builds",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the test suite runs (faster, but ships unverified)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.skip_tests and not args.test_only:
        ok = run_backend_tests()
        ok = run_frontend_tests() == 0 and ok
        if ok != 0:
            sys.exit("Tests failed. Aborting build.")
    elif args.test_only:
        return run_backend_tests() or run_frontend_tests()

    if args.test_only:
        return 0
    if args.backend:
        return run_backend()
    if args.frontend:
        return run_frontend()
    return run_frontend() or run_backend()


if __name__ == "__main__":
    sys.exit(main())