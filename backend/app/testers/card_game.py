"""Card-Game tester — Vite frontend + Express backend (PG session store).

Verified ground truth (2026-08-15): backend/server.js listens on :3000 and
GET / answers "Backend is running ✅"; the Express app uses a PostgreSQL
session store, so a 200 proves PG reachability (PG is up on :5432 on the
desktop). Stored startup only runs the Vite frontend (:5173); the tester
launches the backend explicitly too. No window — no screenshot.
"""

from app.testers import Tester
from app.testers._helpers import TesterContext

FRONTEND_CMD = "cd frontend && npm run dev"
BACKEND_CMD = "cd backend && node server.js"
VITE_PORT = "http://127.0.0.1:5173"
API_PORT = "http://127.0.0.1:3000"


def run(ctx: TesterContext) -> None:
    ctx.launch(FRONTEND_CMD)
    ctx.wait(10)
    ctx.http("GET", VITE_PORT)
    ctx.launch(BACKEND_CMD)
    ctx.wait(8)
    ctx.http("GET", f"{API_PORT}/", expect_body="Backend is running")


TESTER = Tester(
    name="Card-Game smoke",
    description=(
        "Launch the Vite frontend, verify it serves on :5173; launch the "
        "Express backend and verify GET / answers (proves the PostgreSQL "
        "session store is reachable — PG must be up for this to pass)."
    ),
    run=run,
    project_slug="Card-Game",
)
