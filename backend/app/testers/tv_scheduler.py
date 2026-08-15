"""TV-Scheduler tester — Electron app + Express backend (:3050).

Verified ground truth (2026-08-15): backend/server.js listens on :3050 and
logs "Local backend running at http://localhost:3050" on start. The startup
command launches backend + frontend + Electron concurrently.
"""

from app.testers import Tester
from app.testers._helpers import TesterContext

STARTUP_CMD = (
    'concurrently "npm run backend" "npm run frontend" '
    '"wait-on http://localhost:5173 && npm run electron"'
)
PORT = "http://127.0.0.1:3050"


def run(ctx: TesterContext) -> None:
    ctx.launch(STARTUP_CMD)
    ctx.wait(15)
    ctx.http("GET", PORT)
    ctx.wait(8)
    ctx.screenshot("Electron window with scheduler UI")


TESTER = Tester(
    name="TV-Scheduler smoke",
    description=(
        "Launch the full app (backend + frontend + Electron), verify the "
        "Express backend responds on :3050, and screenshot the window."
    ),
    run=run,
    project_slug="Tv-Scheduler",
)
