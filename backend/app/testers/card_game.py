"""Card-Game tester — Vite frontend + Express backend (SQLite storage).

Verified ground truth (2026-08-16, v1.17.13.3): the backend was migrated from
PostgreSQL to local better-sqlite3 (backend/cardgame.db, gitignored, schema
self-provisions from schema.sql on first open; sessions live in the same
file via a custom SQLite express-session store). backend/server.js listens on
:3000 and GET / answers "Backend is running ✅". First live runs (2026-08-16,
v1.17.13.2) exposed two real issues, both caught honestly by the tester:
(1) Vite v8 binds `localhost` on IPv6 (`::1`) here, so the hardcoded
`127.0.0.1` refused — the tester now targets `http://localhost:5173`, which
resolves to whatever the dev server actually binds. (2) The backend's
`DATABASE_URL` (dotenvx, in backend/.env) pointed at a cloud Postgres host
that no longer resolved (ENOTFOUND postgres.fkrujiganyahxadezqdz… —
dead/expired endpoint): the Express server printed "Server running on 3000"
then died on the first pool query (Node ≥22 exits on unhandled rejection),
so the backend check failed with connection refused. Fixed app-side by the
SQLite migration (DATABASE_URL deleted; local PG is unrelated to the app).
Stored startup only runs the Vite frontend (:5173); the tester launches the
backend explicitly too. Browser-served — the tester registers a headless
render of the frontend as the session screenshot.
"""

from app.testers import Tester
from app.testers._helpers import TesterContext

FRONTEND_CMD = "cd frontend && npm run dev"
BACKEND_CMD = "cd backend && node server.js"
VITE_PORT = "http://localhost:5173"
API_PORT = "http://127.0.0.1:3000"


def run(ctx: TesterContext) -> None:
    ctx.launch(FRONTEND_CMD)
    ctx.wait(10)
    ctx.http("GET", VITE_PORT, retries=5)
    ctx.launch(BACKEND_CMD)
    ctx.wait(8)
    ctx.http("GET", f"{API_PORT}/", expect_body="Backend is running", retries=5)
    # v1.17.13.2: browser-served app — capture the first screen headlessly.
    ctx.render_and_register(VITE_PORT, "headless dashboard render")


TESTER = Tester(
    name="Card-Game smoke",
    description=(
        "Launch the Vite frontend, verify it serves on :5173; launch the "
        "Express backend and verify GET / answers (proves the local SQLite "
        "storage — backend/cardgame.db — is up; the app needs no external "
        "database); render the frontend headlessly and register the frame as "
        "a session screenshot."
    ),
    run=run,
    project_slug="Card-Game",
)
