"""Dinner Menu Generator tester — Vite frontend + Flask backend (:5000).

Verified ground truth (2026-08-15): backend/app.py runs Flask on :5000
(global python; no repo venv); stored startup only runs the Vite frontend
(:5173), so the tester launches the Flask backend explicitly. The app
auto-opens a browser tab on start — expected, harmless.

v1.17.13.7: vite 8 binds loopback as IPv6-only (::1) — 127.0.0.1 is refused;
the frontend must be probed via `localhost` (Card-Game's tester already
uses it; dinner menu's first live run failed with WinError 10061).
"""

from app.testers import Tester
from app.testers._helpers import TesterContext

FRONTEND_CMD = "cd frontend && npm run dev"
BACKEND_CMD = "cd backend && python app.py"
VITE_PORT = "http://localhost:5173"
FLASK_PORT = "http://127.0.0.1:5000"


def run(ctx: TesterContext) -> None:
    ctx.launch(FRONTEND_CMD)
    # v1.17.18.6 (audit2 T10): bounded retries instead of a fixed sleep —
    # Vite cold re-optimization races fixed waits on this machine (the
    # Card-Game tester proved the retries pattern live).
    ctx.http("GET", VITE_PORT, retries=4)
    ctx.launch(BACKEND_CMD)
    ctx.http("GET", FLASK_PORT, retries=4)


TESTER = Tester(
    name="Dinner Menu smoke",
    description=(
        "Launch the Vite frontend, verify :5173 serves; launch the Flask "
        "backend and verify GET / on :5000 responds. (The app auto-opens a "
        "browser tab on start.)"
    ),
    run=run,
    project_slug="Dinner-Menu-Generator",
    web_url=VITE_PORT,
    extra_launch=(BACKEND_CMD,),
    ports=(5173, 5000),
)
