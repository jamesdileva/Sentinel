#!/usr/bin/env python
"""Project Sentinel — dev build helper (Sprint 15, docs/02 §12.6).

Deterministic local verification + artifact build, no Docker:
  1. Backend: pytest, black --check, isort --check, flake8.
  2. Frontend: npm run build (tsc + vite), eslint via the project's lint script.
  3. [--dist] Copy the built frontend into backend/static AND rebuild the
     frozen backend bundle (desktop/resources/server-runtime) that the
     desktop installer ships.
  4. [--desktop] Build the Electron win-unpacked folder + NSIS installer
     (desktop/dist) on top of the freshly built server bundle.

Usage:
    python scripts/build.py            # verify everything, build nothing
    python scripts/build.py --dist     # verify, stage frontend + server bundle
    python scripts/build.py --dist --desktop   # ... + installer artifacts
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
DESKTOP = ROOT / "desktop"
STATIC_TARGET = BACKEND / "app" / "static"
SERVER_SPEC = DESKTOP / "server" / "sentinel-server.spec"

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
    ok = run_python(["-m", "black", "--check", "app", "tests"]) == 0
    ok = run_python(["-m", "isort", "--check-only", "app", "tests"]) == 0 and ok
    ok = (
        run_python(["-m", "flake8", "--max-line-length=100", "app", "tests"]) == 0
        and ok
    )
    return 0 if ok else 1


def run_frontend_tests() -> int:
    return run(["npm", "run", "test"], cwd=FRONTEND)


def build_frontend() -> int:
    return run(["npm", "run", "build"], cwd=FRONTEND)


def build_server_bundle() -> int:
    """Rebuild the frozen backend (PyInstaller onedir) that the desktop
    installer ships. Skips with a loud note when PyInstaller isn't installed
    so machines that never package still get a working --dist."""
    if not SERVER_SPEC.exists():
        print("No server spec — skipping frozen-backend build.")
        return 0
    if run_python(["-c", "import PyInstaller"]) != 0:
        print(
            "PyInstaller not installed — frozen backend NOT rebuilt "
            "(installer would ship a stale server). Install with:\n"
            f"  {BACKEND / '.venv' / 'Scripts' / 'python.exe'} -m pip install pyinstaller"
        )
        return 0
    return run_python(
        [
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--distpath",
            str(DESKTOP / "resources"),
            "--workpath",
            str(ROOT / "build" / "server"),
            str(SERVER_SPEC),
        ],
        cwd=ROOT,
    )


def build_desktop() -> int:
    """Electron win-unpacked + NSIS installer from the current bundle."""
    return run(["npm", "run", "dist"], cwd=DESKTOP)


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
        help="Stage the frontend + rebuild the frozen backend bundle",
    )
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Build the Electron installer from the current server bundle "
        "(implies rebuilding that bundle)",
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
        ok = run_backend_tests() == 0
        ok = run_frontend_tests() == 0 and ok
        ok = lint_backend() == 0 and ok
        if not ok:
            sys.exit("Tests failed. Aborting build.")
    ok = build_frontend() == 0

    if args.dist:
        ok = stage_frontend() == 0 and ok
        ok = build_server_bundle() == 0 and ok

    # --desktop implies a fresh server bundle (the installer ships it).
    if args.desktop and not args.dist:
        ok = build_server_bundle() == 0 and ok
    if args.desktop:
        ok = build_desktop() == 0 and ok

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
