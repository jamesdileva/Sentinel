#!/usr/bin/env python
"""Project Sentinel — dev build helper (Sprint 15, docs/02 §12.6).

Deterministic local verification + artifact build, no Docker:
  1. Backend: pytest, black --check, isort --check, flake8.
  2. Frontend: npm run build (tsc + vite), eslint via the project's lint script.
  3. [--dist] Copy the built frontend into backend/static so the backend
     serves the UI directly (native install, docs/laptop.md).

Usage:
    python scripts/build.py            # verify everything, build nothing
    python scripts/build.py --dist     # verify, then stage frontend into backend
    python scripts/build.py --skip-tests  # stage only, skip verification
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
STATIC_TARGET = BACKEND / "app" / "static"

_PY_BIN = BACKEND / ".venv" / "Scripts" / "python.exe"
if not _PY_BIN.exists():
    _PY_BIN = BACKEND / ".venv" / "bin" / "python3"


def run(argv: list[str], cwd: Path = ROOT) -> int:
    """Run a command, returning its exit code.

    On Windows, .cmd/.bat shims (npm) are resolved through cmd so they
    actually launch (subprocess cannot spawn bare `npm` without cmd).
    """
    print(f"$ {' '.join(argv)}")
    if os.name == "nt":
        return subprocess.run(["cmd", "/c", *argv], cwd=cwd).returncode
    return subprocess.run(argv, cwd=cwd).returncode


def run_python(argv: list[str], cwd: Path = BACKEND) -> int:
    return run([str(_PY_BIN), *argv], cwd=cwd)


def run_backend_tests() -> int:
    return run_python(["-m", "pytest", "tests", "--quiet"])


def lint_backend() -> int:
    ok = run_python(["-m", "black", "--check", "app", "tests"])
    ok = run_python(["-m", "isort", "--check-only", "app", "tests"]) == 0 and ok
    ok = run_python(["-m", "flake8", "app", "tests"]) == 0 and ok
    return 0 if ok else 1


def run_frontend_tests() -> int:
    return run(["npm", "run", "test"], cwd=FRONTEND)


def build_frontend() -> int:
    return run(["npm", "run", "build"], cwd=FRONTEND)


def stage_frontend() -> int:
    """Copy the vite build output into backend/app/static for local serving."""
    dist = FRONTEND / "dist"
    if not dist.is_dir():
        sys.exit("frontend/dist missing — run 'npm run build' first.")
    STATIC_TARGET.mkdir(parents=True, exist_ok=True)
    for child in STATIC_TARGET.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in dist.iterdir():
        target = STATIC_TARGET / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target)
    print(
        f"Staged frontend into backend/app/static ({len(list(dist.iterdir()))} entries)"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build.py", description=__doc__)
    parser.add_argument(
        "--dist",
        action="store_true",
        help="Stage the built frontend into backend/app/static",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip test suites (faster, but ships unverified)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.skip_tests:
        ok = run_backend_tests()
        ok = run_frontend_tests() == 0 and ok
        ok = lint_backend() == 0 and ok
        if ok != 0:
            sys.exit("Tests failed. Aborting build.")
    ok = build_frontend() == 0

    if args.dist:
        ok = stage_frontend() == 0 and ok

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
