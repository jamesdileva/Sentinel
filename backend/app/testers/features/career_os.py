"""Career OS click-through feature — packaged Electron app + live backend.

Drives the packaged desktop app (frontend/dist/win-unpacked/Career
OS.exe) over the CDP-attached FeatureRunner. Unlike the other electron
apps, Career OS's renderer is a thin client: it fetches everything from
its FastAPI backend (baked-in base URL http://127.0.0.1:8000/api/v1), so
the feature owns the backend process — it spawns uvicorn from the
project's own venv, waits for /health, drives the UI against live data,
and tears down ONLY the PID tree it spawned (never taskkill by image
name — FeatureRunner owns the exe itself). If a healthy backend already
serves :8000 it is reused and nothing is spawned.

UI ground truth (2026-08-22 source scan):
- Layout sidebar (components/layout.tsx): h1 "Career OS"; NavLinks
  Dashboard, Import, Resume Builder, SOQ Builder, Duty Statement,
  Explorer.
- Dashboard (pages/Dashboard.tsx): h2 "Dashboard" + intro copy.
- Explorer (pages/KnowledgeExplorer.tsx): h2 "Evidence Explorer",
  debounced search; ResultsList renders li[data-testid="result-item"]
  nodes once the browse-mode query lands (empty query = browse mode).

The sandboxed --user-data-dir instance still writes its boot marker
(career-os.log in userData, written by electron/main.cjs) so Sentinel's
sandbox verification passes without touching the real profile.
"""

import os
import subprocess
import time
from pathlib import Path

import httpx

from app.testers._helpers import TesterEnvError
from app.testers.features import Feature, FeatureContext

BACKEND_REL = Path("backend") / ".venv" / "Scripts" / "python.exe"
API_BASE = "http://127.0.0.1:8000"
HEALTH_WAIT_S = 30


def _backend_healthy() -> bool:
    try:
        response = httpx.get(f"{API_BASE}/health", timeout=3)
    except httpx.HTTPError:
        return False
    return response.status_code == 200 and "healthy" in response.text


def _spawn_backend(ctx: FeatureContext) -> subprocess.Popen:
    """Spawn uvicorn from the project's own venv (cwd=backend)."""
    python = Path(ctx.project.path) / BACKEND_REL
    if not python.exists():
        raise TesterEnvError(
            f"Career OS backend interpreter missing: {python} "
            '(create it via pip install -e ".[dev]")'
        )
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--port",
            "8000",
        ],
        cwd=str(python.parent.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
        env=env,
    )


def _wait_backend(proc: subprocess.Popen) -> None:
    deadline = time.monotonic() + HEALTH_WAIT_S
    while not _backend_healthy():
        if proc.poll() is not None:
            raise TesterEnvError(
                f"Career OS backend exited during startup (code {proc.returncode})"
            )
        if time.monotonic() > deadline:
            raise TesterEnvError(
                f"Career OS backend not healthy on :8000 within {HEALTH_WAIT_S}s"
            )
        time.sleep(1)


def _stop_backend(proc: subprocess.Popen) -> None:
    try:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def run(ctx: FeatureContext) -> None:
    proc = None
    if _backend_healthy():
        ctx.step("reusing the Career OS backend already serving :8000")
    else:
        proc = _spawn_backend(ctx)
        _wait_backend(proc)
        ctx.step("Career OS backend healthy on :8000")
    try:
        page = ctx.page
        page.get_by_role("heading", name="Career OS").wait_for(
            state="visible", timeout=15000
        )
        ctx.step("dashboard shell rendered")
        ctx.shot("Career OS dashboard")

        page.get_by_role("link", name="Explorer").click()
        page.get_by_role("heading", name="Evidence Explorer").wait_for(
            state="visible", timeout=15000
        )
        results = page.locator('[data-testid="result-item"]')
        results.first.wait_for(state="visible", timeout=30000)
        count = results.count()
        ctx.step(f"Explorer browse returned {count} knowledge items")
        ctx.shot("Explorer search results over the live corpus")
    finally:
        if proc is not None:
            _stop_backend(proc)
            ctx.step("spawned backend torn down (own PID tree only)")


FEATURES = [
    Feature(
        name="Career OS dashboard + Explorer click-through",
        description=(
            "Spawn the FastAPI backend from the project venv, wait for "
            "/health, then drive the packaged Electron window over CDP: "
            "assert the dashboard shell renders non-blank, navigate to the "
            "Evidence Explorer via the sidebar and assert real search "
            "results render against the live corpus. Only the backend PID "
            "tree this feature spawned is ever killed."
        ),
        run=run,
        electron=True,
        budget_s=180,
    ),
]
