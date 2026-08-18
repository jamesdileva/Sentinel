"""TV-Scheduler tester — packaged app presence + dev-stack click-through.

The packaged app (dist/win-unpacked/TV Scheduler.exe) is auto-launched by
the runner and its Express backend on :3050 is probed via /health — the
backend serves the API + /health only (the frontend is loaded by Electron
from app.asar, loadFile; GET / is 404 by design).

v1.17.13.6: replaced the old dev-stack launch (concurrently is not on PATH
and would collide with the packaged app on :3050) and the GET / assertion
(no such route) with a /health probe of the auto-launched app.

v1.17.14.1 live-fix: the click-through features drive the dev UI
(localhost:5173 — vite 8 binds ::1, not 127.0.0.1) whose App.jsx
hardcodes `API_BASE_URL = http://127.0.0.1:3050`. The packaged app's own
add-show path is broken (manual fallback inserts a TEXT id into the
INTEGER PRIMARY KEY watchlist.showId — SQLITE_MISMATCH; repo fixes pending
user rebuild), so after the presence probe the tester reclaims :3050 from
the auto-launched instance (taskkill, the port-listener pattern approved
for build->open) and runs the current dev stack: `node backend/server.js`
on :3050 + vite on :5173. The features then exercise the app's real code
(its own userData-free repo DB; self-created entities only).
"""

from app.testers import Tester
from app.testers._helpers import TesterContext

HEALTH_URL = "http://127.0.0.1:3050/health"
DEV_UI_CMD = "cd frontend && npm run dev"
DEV_API_CMD = "node backend/server.js"


def run(ctx: TesterContext) -> None:
    ctx.http("GET", HEALTH_URL, retries=2)
    ctx.wait(8)
    ctx.screenshot("Electron window with scheduler UI")
    ctx.cli('taskkill /IM "TV Scheduler.exe" /F')
    ctx.launch(DEV_API_CMD)
    ctx.launch(DEV_UI_CMD)
    ctx.http("GET", "http://127.0.0.1:3050/health", retries=4)
    ctx.http("GET", "http://localhost:5173", retries=4)


TESTER = Tester(
    name="TV-Scheduler smoke",
    description=(
        "Verify the packaged app's Express backend responds on :3050 "
        "(/health), screenshot the Electron window, then swap in the dev "
        "stack (server.js on :3050 + vite on :5173) for the click-through "
        "features."
    ),
    run=run,
    project_slug="Tv-Scheduler",
    web_url="http://localhost:5173",
    extra_launch=(DEV_API_CMD, DEV_UI_CMD),
    ports=(3050, 5173),
)
