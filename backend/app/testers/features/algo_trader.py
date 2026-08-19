"""ALGO-TRADER dashboard click-through feature (docs/clickthrough_plan.md).

Locator ground truth (2026-08-18): the dashboard is a single index.html
card grid — h1 "ALGO TRADER", stat values in #equity/#cash/#total-pnl/
#win-rate, tables populated into #positions-table/#selections-table/
#trades-table/#orders-table/#rejections-table. loadAll() fills
everything and sets #last-update to "Updated: <time>" only after ALL
fetch()s resolve — including /api/positions/live (the app's own
read-only Alpaca paper-API call, ≤5 s urlopen timeout; Rule 1 note in
the tester module docstring). The feature waits for that marker, then
asserts local-DB sections only (equity stat + orders table rows).
Read-only: no orders or trades are ever placed.
"""

from app.testers._helpers import TesterAssertionError
from app.testers.features import Feature, FeatureContext

APP_URL = "http://127.0.0.1:5000"  # Flask binds 127.0.0.1 by default
UPDATED_MARKER = "Updated:"


def _dashboard_renders(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)

    page.get_by_role("heading", name="ALGO TRADER").wait_for(
        state="visible", timeout=15000
    )
    ctx.step("dashboard heading visible")

    page.locator("#last-update", has_text=UPDATED_MARKER).wait_for(
        state="visible", timeout=20000
    )
    ctx.step("loadAll() completed (Updated: marker set)")

    equity = page.locator("#equity").inner_text()
    if equity in ("--", "Loading..."):
        raise TesterAssertionError(f"equity stat never populated ({equity!r})")
    ctx.step(f"equity stat populated: {equity}")

    orders = page.locator("#orders-table tr").count()
    if orders == 0:
        raise TesterAssertionError("orders table has no rows")
    ctx.step(f"orders table rendered {orders} rows")

    ctx.shot("dashboard with populated tables")


FEATURES = [
    Feature(
        "dashboard renders with local data",
        "Open the Flask dashboard, wait for loadAll() to complete "
        "(Updated: marker), then assert the equity stat is populated and "
        "the orders table has rows — all read-only local SQLite data.",
        _dashboard_renders,
    ),
]
