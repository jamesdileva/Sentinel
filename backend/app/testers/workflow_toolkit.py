"""WorkFlow-Toolkit tester — Electron + FastAPI backend (uvicorn on :8000).

Verified ground truth (2026-08-15): startup launches frontend dev + backend
`python -m uvicorn app.main:app` (default port 8000 — the same port CG and
Demake use, so a tester run while another 8000-bound app is up reports
investigate honestly).
"""

from app.testers import Tester
from app.testers._helpers import TesterContext

STARTUP_CMD = (
    'concurrently "npm --prefix frontend run dev" '
    '"cd backend && python -m uvicorn app.main:app --reload"'
)
PORT = "http://127.0.0.1:8000"


def run(ctx: TesterContext) -> None:
    ctx.launch(STARTUP_CMD)
    ctx.wait(15)
    ctx.http("GET", f"{PORT}/health")
    ctx.wait(8)
    ctx.screenshot("WorkFlow-Toolkit window")


TESTER = Tester(
    name="WorkFlow-Toolkit smoke",
    description=(
        "Launch frontend + backend, verify the FastAPI backend /health on "
        ":8000, and screenshot the Electron window. Port 8000 is shared with "
        "CG/Demake — a conflicting instance reports investigate."
    ),
    run=run,
    project_slug="Workflow-Toolkit",
)
