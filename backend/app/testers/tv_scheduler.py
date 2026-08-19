"""TV-Scheduler tester — packaged app presence + window capture.

The packaged app (dist/win-unpacked/TV Scheduler.exe) is auto-launched by
the runner and its Express backend on :3050 is probed via /health — the
backend serves the API + /health only (the frontend is loaded by Electron
from app.asar, loadFile; GET / is 404 by design). The window is captured
by the runner's auto-launch hook; the click-through features then drive
the real window (Phase 2, v1.17.14.4): the FeatureRunner reclaims this
instance and relaunches a sandboxed copy for its own session.

v1.17.13.6: replaced the old dev-stack launch (concurrently is not on PATH
and would collide with the packaged app on :3050) and the GET / assertion
(no such route) with a /health probe of the auto-launched app.

v1.17.14.1 interim: the features drove the dev UI (localhost:5173) because
the packaged app's add-show path was broken (manual fallback inserts a
TEXT id into the INTEGER PRIMARY KEY watchlist.showId — SQLITE_MISMATCH;
repo fixes pending user rebuild). v1.17.14.4 removes that fallback — Phase
2 drives the packaged window directly and real TVMaze names do not hit the
fallback path.
"""

from app.testers import Tester
from app.testers._helpers import TesterContext

HEALTH_URL = "http://127.0.0.1:3050/health"


def run(ctx: TesterContext) -> None:
    ctx.http("GET", HEALTH_URL, retries=2)
    ctx.wait(8)
    ctx.screenshot("Electron window with scheduler UI")


TESTER = Tester(
    name="TV-Scheduler smoke",
    description=(
        "Verify the packaged app's Express backend responds on :3050 "
        "(/health) and screenshot the Electron window; the click-through "
        "features then drive the real window (Phase 2)."
    ),
    run=run,
    project_slug="Tv-Scheduler",
    ports=(3050,),
)
