"""Card-Game tester — Vite frontend + Express backend (PG session store).

Verified ground truth (2026-08-15): backend/server.js listens on :3000 and
GET / answers "Backend is running ✅" — but only while its PostgreSQL
connection survives. First live runs (2026-08-16, v1.17.13.2) exposed two
real issues, both caught honestly by the tester: (1) Vite v8 binds
`localhost` on IPv6 (`::1`) here, so the hardcoded `127.0.0.1` refused — the
tester now targets `http://localhost:5173`, which resolves to whatever the
dev server actually binds. (2) The backend's `DATABASE_URL` (dotenvx, in
backend/.env) points at a cloud Postgres host that no longer resolves
(ENOTFOUND postgres.fkrujiganyahxadezqdz… — dead/expired endpoint): the
Express server prints "Server running on 3000" then dies on the first pool
query (Node ≥22 exits on unhandled rejection), so the backend check fails
with connection refused. Local PG on :5432 is NOT what the app uses — fixing
the app's DATABASE_URL (or provisioning its schema on local PG) is app-side
work, not tester work. Stored startup only runs the Vite frontend (:5173);
the tester launches the backend explicitly too. Browser-served — the tester
registers a headless render of the frontend as the session screenshot.
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
        "Express backend and verify GET / answers (proves the PostgreSQL "
        "session store is reachable — PG must be up for this to pass); "
        "render the frontend headlessly and register the frame as a session "
        "screenshot."
    ),
    run=run,
    project_slug="Card-Game",
)
