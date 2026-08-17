"""TV-Scheduler tester — packaged Electron app + Express backend (:3050).

The packaged app (dist/win-unpacked/TV Scheduler.exe) is the system under
test: the runner auto-launches it (auto_launch) and it runs its own Express
backend on :3050. The backend serves the API + /health only — the frontend
is loaded by Electron from app.asar (loadFile), so there is no static root
route (GET / is 404 by design).

v1.17.13.6: replaced the old dev-stack launch (concurrently is not on PATH
and would collide with the packaged app on :3050) and the GET / assertion
(no such route) with a /health probe of the auto-launched app.
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
        "(/health) and screenshot the Electron window."
    ),
    run=run,
    project_slug="Tv-Scheduler",
)
