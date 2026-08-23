"""Betsim click-through features — Monte Carlo betting simulator (Electron).

Phase: Tier 2 electron engine. The FeatureRunner relaunches the packaged
exe (`release/win-unpacked/Betsim.exe`) with CDP attached and a sandboxed
`--user-data-dir`, and the features below drive the app's real React UI.

Verified ground truth (2026-08-22):
- launch: packaged by electron-builder to release/win-unpacked/Betsim.exe;
  the FeatureRunner owns launching (CDP + --user-data-dir sandbox)
- port 8000, no auth; the backend (FastAPI uvicorn) is spawned BY the exe
  itself from the repo's `.venv` when present, with BETSIM_DB_PATH pointed
  INSIDE the CDP sandbox -> every run starts on a fresh database, so the
  onboarding walkthrough shows on "/" every time and must be dismissed
  before anything else ("Next" x3 then "Try it yourself")
- window title "Betsim" (renderer <title>) - informational only, the
  electron engine attaches over CDP and does not need it
- cleanup: taskkill /IM Betsim.exe /T (tree kill takes the spawned uvicorn
  down with it)
- fallback: without a sibling .venv the UI still renders but shows
  "Backend unreachable"; the workspace feature fails honestly at its Run
  assertion instead of passing vacuously

Locator ground truth (from frontend/src, same DOM as dev stack):
- nav: <a> links labelled Simulation / Strategies / History / Analytics /
  Portfolio / System Plays / Parlay / Settings
- workspace: h1 "Bet parameters", "Run Simulation" button, metric cards
  rendered as [data-testid=metric-*] after a successful run, Recharts
  surfaces for trajectory + distribution
- fresh-DB empty states are asserted as-is where deterministic (Strategies,
  Analytics); destructive actions are never needed (Rule: self-created
  entities only)
"""

import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.testers._helpers import TesterAssertionError
from app.testers.features import Feature, FeatureContext

METRIC_TIMEOUT_MS = 60_000


def _dismiss_onboarding(ctx: FeatureContext) -> None:
    """The sandboxed instance always launches with a fresh localStorage, so
    the first-run walkthrough covers "/" until explicitly completed."""
    page = ctx.page
    dialog = page.get_by_role("dialog", name="Onboarding")
    try:
        dialog.wait_for(state="visible", timeout=5_000)
    except PlaywrightTimeoutError:
        return  # already dismissed in this session
    ctx.step("onboarding walkthrough visible")
    while True:
        next_btn = page.get_by_role("button", name="Next")
        if next_btn.count() == 0:
            break
        next_btn.first.click()
    finish = page.get_by_role("button", name="Try it yourself")
    if finish.count():
        finish.click()
    dialog.wait_for(state="hidden", timeout=10_000)
    ctx.step("onboarding dismissed")


def _wait_backend_healthy(ctx: FeatureContext) -> None:
    """The exe spawns uvicorn itself; give it up to 30s to bind :8000."""
    import time

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            response = ctx.page.request.get("http://127.0.0.1:8000/api/health")
            if response.ok:
                ctx.step("backend healthy (spawned by the packaged exe)")
                return
        except Exception:  # noqa: S110 - retry until the deadline
            pass
        time.sleep(1)
    raise TesterAssertionError("backend never became healthy on :8000")


def _workspace_end_to_end(ctx: FeatureContext) -> None:
    page = ctx.page
    _dismiss_onboarding(ctx)
    _wait_backend_healthy(ctx)

    run_button = page.get_by_role("button", name="Run Simulation")
    run_button.wait_for(state="visible", timeout=15_000)
    ctx.step("workspace ready with default bet parameters")

    # default payload: -110 @ 55%, $1000 bankroll, flat $50, 100 bets x 5000
    run_button.click()
    ctx.step("simulation submitted")

    win_pct = page.locator('[data-testid="metric-win-pct"]')
    win_pct.wait_for(state="visible", timeout=METRIC_TIMEOUT_MS)
    ctx.step(f"win % card rendered ({win_pct.inner_text().strip()})")

    ruin = page.locator('[data-testid="metric-risk-of-ruin"]')
    ruin.wait_for(state="visible", timeout=15_000)
    ctx.step(f"risk-of-ruin card rendered ({ruin.inner_text().strip()})")

    chart = page.locator(".recharts-surface").first
    chart.wait_for(state="visible", timeout=30_000)
    ctx.shot("simulation results with metric cards and charts")


def _screen_tour(ctx: FeatureContext) -> None:
    page = ctx.page
    _dismiss_onboarding(ctx)

    screens = [
        ("Strategies", "No saved strategies yet"),
        ("History", "Results History"),
        ("Analytics", "No backtested predictions yet"),
        ("Portfolio", None),
        ("System Plays", "Calibrate Model"),
        ("Parlay", "Run Parlay Simulation"),
        ("Settings", "Save Settings"),
    ]
    for link_name, anchor in screens:
        page.get_by_role("link", name=link_name).click()
        if link_name == "Portfolio":
            marker = page.get_by_label("Bankroll ($)")
            anchor_text = "bankroll input"
        else:
            marker = page.get_by_text(anchor).first
            anchor_text = anchor
        marker.wait_for(state="visible", timeout=20_000)
        ctx.step(f"{link_name} screen renders its anchor ({anchor_text})")
        ctx.shot(f"{link_name} screen")

    # back home: workspace placeholder returns (fresh run, nothing persisted)
    page.get_by_role("link", name="Simulation").click()
    page.locator('[data-testid="results-placeholder"]').first.wait_for(
        state="visible", timeout=20_000
    )
    ctx.step("returned to the workspace")
    ctx.shot("workspace idle state")


FEATURES = [
    Feature(
        name="workspace simulation end-to-end",
        description=(
            "Dismiss the first-run walkthrough, wait for the self-spawned "
            "backend, run the default simulation from the workspace form, "
            "and assert the win % / risk-of-ruin metric cards plus the "
            "trajectory/distribution charts render."
        ),
        run=_workspace_end_to_end,
        electron=True,
    ),
    Feature(
        name="screen tour across all tabs",
        description=(
            "Walk the navigation bar through every screen (Strategies, "
            "History, Analytics, Portfolio, System Plays, Parlay, Settings) "
            "asserting each renders its anchor content on a fresh database, "
            "screenshotting each, then returning to the workspace."
        ),
        run=_screen_tour,
        electron=True,
    ),
]
