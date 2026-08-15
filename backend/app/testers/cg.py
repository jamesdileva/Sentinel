"""CG tester — AI Documentary Studio (Electron renderer + FastAPI backend).

Verified ground truth (2026-08-15):
- Backend runs from the repo root via the repo venv:
  `"<repo>\\venv\\Scripts\\python.exe" -m uvicorn backend.main:app` on :8000.
- `LLM_PROVIDER=mock` is pinned in the launch env (observed default differs
  between config and runtime) — topic generation is deterministic (fixed
  MOCK_TOPICS list).
- Backend pytest suite is green (46 passed, ~66s) and runs without the
  server.
- Renderer bug on record: renderer/src/api/client.ts:308 calls
  `/api/pipeline/jobs/{id}` but the server route is `/api/pipeline/job/{id}`
  (backend/api/pipeline.py:88) — a 404 the tester watches for in the app
  log after the Electron launch.
"""

from pathlib import Path

from app.testers import Tester
from app.testers._helpers import TesterAssertionError, TesterContext, TesterEnvError

BACKEND_CMD = '"{}" -m uvicorn backend.main:app'
ELECTRON_CMD = "cd renderer && npm run start"
PYTEST_CMD = 'cd backend && "{}" -m pytest'
PORT = "http://127.0.0.1:8000"


def run(ctx: TesterContext) -> None:
    root = Path(ctx.project.path)
    venv_python = root / "venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        raise TesterEnvError(f"CG venv python missing: {venv_python}")

    ctx.launch(BACKEND_CMD.format(venv_python), env={"LLM_PROVIDER": "mock"})
    ctx.wait_log("Uvicorn running on", 60)
    ctx.http("GET", f"{PORT}/health", expect_body="healthy")
    ctx.http("GET", f"{PORT}/", expect_body="AI Documentary Studio")
    ctx.http("POST", f"{PORT}/api/topics/generate")
    ctx.wait(4)
    # Mock LLM's fixed MOCK_TOPICS make this deterministic.
    ctx.http("GET", f"{PORT}/api/topics", expect_body="Molasses")
    ctx.checkpoint("mock topic generation verified")

    ctx.launch(ELECTRON_CMD)
    ctx.wait(15)
    ctx.screenshot("Electron window after launch")
    # The renderer's `/api/pipeline/jobs/{id}` calls 404 against the server's
    # singular `/api/pipeline/job/{id}` route (known bug, client.ts:308).
    if ctx.log_contains("pipeline/jobs"):
        raise TesterAssertionError(
            "renderer hit /api/pipeline/jobs/ (plural) and 404'd — server "
            "route is /api/pipeline/job/ (singular); see "
            "renderer/src/api/client.ts:308"
        )

    ctx.pytest(PYTEST_CMD.format(venv_python), cwd=str(root), timeout_s=300)


TESTER = Tester(
    name="CG backend + Electron",
    description=(
        "Launch the FastAPI backend (mock LLM, deterministic topics) and "
        "verify /health, / and /api/topics; generate a topic and confirm the "
        "golden mock topic appears; launch the Electron renderer, screenshot "
        "it, and watch for the renderer's known /api/pipeline/jobs 404; run "
        "the backend pytest suite (46 tests)."
    ),
    run=run,
    project_slug="Cg",
)
