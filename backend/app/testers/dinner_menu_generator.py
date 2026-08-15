"""Dinner Menu Generator tester — Vite frontend + Flask backend (:5000).

Verified ground truth (2026-08-15): backend/app.py runs Flask on :5000
(global python; no repo venv); stored startup only runs the Vite frontend
(:5173), so the tester launches the Flask backend explicitly. The app
auto-opens a browser tab on start — expected, harmless.
"""

from app.testers import Tester
from app.testers._helpers import TesterContext

FRONTEND_CMD = "cd frontend && npm run dev"
BACKEND_CMD = "cd backend && python app.py"
VITE_PORT = "http://127.0.0.1:5173"
FLASK_PORT = "http://127.0.0.1:5000"


def run(ctx: TesterContext) -> None:
    ctx.launch(FRONTEND_CMD)
    ctx.wait(10)
    ctx.http("GET", VITE_PORT)
    ctx.launch(BACKEND_CMD)
    ctx.wait(8)
    ctx.http("GET", FLASK_PORT)


TESTER = Tester(
    name="Dinner Menu smoke",
    description=(
        "Launch the Vite frontend, verify :5173 serves; launch the Flask "
        "backend and verify GET / on :5000 responds. (The app auto-opens a "
        "browser tab on start.)"
    ),
    run=run,
    project_slug="Dinner-Menu-Generator",
)
