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

2026-08-22: added Tier-1 API assertions — after the health checks the tester
drives the real HTTP API end to end (register -> login -> spin -> coinflip
-> highlow start+guess -> open-crate basic), asserting status codes and key
JSON fields with a throwaway api-tester-<ts> account. Sessions are cookie
based; httpx.Client keeps the jar automatically.
"""

import time

import httpx

from app.testers import Tester
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
)

FRONTEND_CMD = "cd frontend && npm run dev"
BACKEND_CMD = "cd backend && node server.js"
VITE_PORT = "http://localhost:5173"
API_PORT = "http://127.0.0.1:3000"
API_BASE = f"{API_PORT}/api"


def _api_assertions(ctx: TesterContext) -> None:
    """Drive the game API end to end over HTTP (Tier 1, headless)."""
    # app-side validation allows [a-zA-Z0-9_] only — no hyphens
    username = f"api_tester_{time.time_ns() % 10**9}"

    def expect(cond, message):
        if not cond:
            raise TesterAssertionError(message)
        ctx.checkpoint(message)

    with httpx.Client(base_url=API_BASE, timeout=15.0) as client:
        r = client.post(
            "/auth/register",
            json={"username": username, "password": "api-pass-1"},
        )
        if r.status_code != 200 or not r.json().get("success"):
            raise TesterAssertionError(
                f"register failed: {r.status_code} {r.text[:120]}"
            )
        ctx.checkpoint("api register ok")

        r = client.post(
            "/auth/login", json={"username": username, "password": "api-pass-1"}
        )
        body = r.json() if r.status_code == 200 else {}
        expect(
            r.status_code == 200 and body.get("status") == "logged_in", "api login ok"
        )

        # validation still guards bad input (400)
        r = client.post("/game/spin", json={"bet": -5})
        expect(r.status_code == 400, "api rejects invalid bet")

        r = client.post("/game/spin", json={"bet": 10})
        body = r.json() if r.status_code == 200 else {}
        expect(
            r.status_code == 200
            and isinstance(body.get("reels"), list)
            and isinstance(body.get("payout"), int)
            and isinstance(body.get("balance"), int),
            "api spin returns reels/payout/balance",
        )

        r = client.post("/game/coinflip", json={"bet": 10, "choice": "heads"})
        body = r.json() if r.status_code == 200 else {}
        expect(
            r.status_code == 200
            and body.get("flip") in ("heads", "tails")
            and isinstance(body.get("win"), bool)
            and isinstance(body.get("payout"), int),
            "api coinflip returns flip/win/payout",
        )

        r = client.post("/game/highlow", json={"action": "start"})
        base = (r.json() or {}).get("number") if r.status_code == 200 else None
        expect(
            r.status_code == 200 and isinstance(base, int) and 1 <= base <= 100,
            "api highlow start rolls 1-100",
        )

        direction = "lower" if base == 100 else "higher"
        r = client.post(
            "/game/highlow",
            json={"action": "guess", "direction": direction, "bet": 10},
        )
        body = r.json() if r.status_code == 200 else {}
        expect(
            r.status_code == 200
            and isinstance(body.get("win"), bool)
            and isinstance(body.get("mult"), (int, float))
            and isinstance(body.get("payout"), int),
            "api highlow guess resolves",
        )

        r = client.post("/game/open-crate", json={"type": "basic"})
        body = r.json() if r.status_code == 200 else {}
        rewards = body.get("rewards")
        expect(
            r.status_code == 200
            and isinstance(rewards, list)
            and len(rewards) >= 2
            and all("id" in item and "rarity" in item for item in rewards),
            "api open-crate basic grants rewards",
        )

        r = client.post("/game/open-crate", json={"type": "mythic"})
        expect(r.status_code == 400, "api rejects unknown crate type")


def run(ctx: TesterContext) -> None:
    ctx.launch(FRONTEND_CMD)
    ctx.wait(10)
    ctx.http("GET", VITE_PORT, retries=5)
    ctx.launch(BACKEND_CMD)
    ctx.wait(8)
    ctx.http("GET", f"{API_PORT}/", expect_body="Backend is running", retries=5)

    # Tier-1: exercise the gameplay API before rendering the UI.
    try:
        _api_assertions(ctx)
    except TesterAssertionError:
        raise
    except Exception as exc:  # connection issues etc. -> env problem
        raise TesterEnvError(f"API assertion block failed: {exc}") from exc

    # v1.17.13.2: browser-served app — capture the first screen headlessly.
    ctx.render_and_register(VITE_PORT, "headless dashboard render")


TESTER = Tester(
    name="Card-Game smoke",
    description=(
        "Launch the Vite frontend, verify it serves on :5173; launch the "
        "Express backend and verify GET / answers (proves the local SQLite "
        "storage — backend/cardgame.db — is up; the app needs no external "
        "database); drive the gameplay HTTP API end to end with a throwaway "
        "account (spin, coinflip, highlow, crates incl. rejection paths); "
        "render the frontend headlessly and register the frame as a session "
        "screenshot."
    ),
    run=run,
    project_slug="Card-Game",
    web_url=VITE_PORT,
    extra_launch=(BACKEND_CMD,),
    ports=(5173, 3000),
)
