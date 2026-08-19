"""ALGO-TRADER tester — Flask dashboard (:5000) + backtester.exe CLI smoke.

Verified ground truth (2026-08-18, v1.17.15): the dashboard is Flask
(web/app.py, app.run(debug=True, port=5000)) serving read-only SQLite
views over data/algo_trader.db (521 orders, 243 trades, 588 account
snapshots — populated). The repo has no venv, so the launch command's
`python` passes through unre-written and resolves via PATH (the
machine's system Python, which has Flask 3.1.3).

Rule 1 note: the dashboard's own JS fires /api/positions/live on load —
the app's normal read-only call to Alpaca's paper API using the keys in
config/settings.json. That is the page's own behavior, not a Sentinel
export; Sentinel never asserts on it and carries no credentials.

Deliberate exclusions:
- trader.exe — a live trading loop (reads config/settings.json keys,
  infinite scheduler): not deterministic, excluded (Rule 3).
- The backtester runs a REAL backtest: `cd build && backtester.exe
  2026-07-01 2026-07-24` (run from build/ — the exe resolves
  `../config/settings.json`, `../data/universe.txt` and
  `../data/backtest.db` relative to its own dir; bars confirmed present
  in backtest.db — the DB spans 2025-02-03 → 2026-07-24, so no Alpaca
  calls; the backtester's main() never calls fetchAndStore — DataFeed
  reads bars from the DB only). resetBacktestState wipes and the run
  repopulates only data/backtest.db (the app's own backtest copy —
  data/algo_trader.db, which the dashboard reads, is untouched).
  Completion is asserted on the `=== BACKTEST COMPLETE ===` marker +
  exit 0.

Leftover convention (same as Workflow-Toolkit's :8000 uvicorn): the
launched Flask dashboard keeps serving on :5000 after the session and
is cleaned manually between rounds — the launch shell has no tracked
pid and the tester never kills by broad image name.
"""

from app.testers import Tester
from app.testers._helpers import TesterContext

BACKTEST_START = "2026-07-01"
BACKTEST_END = "2026-07-24"
DASHBOARD_CMD = "cd web && python app.py"
DASHBOARD_URL = "http://127.0.0.1:5000"


def run(ctx: TesterContext) -> None:
    ctx.cli(
        f"cd build && backtester.exe {BACKTEST_START} {BACKTEST_END}",
        timeout_s=300,
        expect_stdout="=== BACKTEST COMPLETE ===",
    )
    ctx.launch(DASHBOARD_CMD)
    ctx.http("GET", DASHBOARD_URL, expect_body="ALGO TRADER", retries=10)
    ctx.http("GET", f"{DASHBOARD_URL}/api/account", expect_body='"equity"', retries=5)
    ctx.http("GET", f"{DASHBOARD_URL}/api/orders/recent")
    ctx.http("GET", f"{DASHBOARD_URL}/api/trades")
    ctx.render_and_register(DASHBOARD_URL, "headless dashboard render")


TESTER = Tester(
    name="ALGO-TRADER smoke",
    description=(
        "Run a real backtest (backtester.exe 2026-07-01 2026-07-24 from "
        "build/ — bars already in backtest.db, so it is fully local; only "
        "the app's own backtest copy is rewritten) and assert the "
        "BACKTEST COMPLETE marker. Launch the Flask dashboard (:5000), "
        "verify / answers, /api/account serves the latest account "
        "snapshot, /api/orders/recent and /api/trades serve (read-only "
        "local SQLite reads), then headless-render the dashboard as "
        "the session screenshot."
    ),
    run=run,
    project_slug="Algo-Trader",
    web_url=DASHBOARD_URL,
    ports=(5000,),
)
