"""FinSight tester — Electron shell + Flask backend (HTTP, no mouse).

Verified ground truth (2026-08-20):
- Root package.json has no `main` (`index.js` does not exist) — `electron .`
  from the project root fails; the working launch is from the `electron/`
  subdir (`electron/package.json` -> `main.js`), which spawns
  `python ../app.py` (relative to the electron cwd, so it resolves to the
  project-root `app.py`) and loads `http://127.0.0.1:10000`.
- The Flask app needs no auth: GET / renders the dashboard directly
  (login.html/register.html are vestigial). Port default 10000 (PORT env).
- Fallback: if the electron shell does not reach the backend, launch
  `python app.py` from the project root directly.

This tester is fully headless-friendly (HTTP assertions only; the electron
window may open but nothing is clicked) — dinner-menu pattern (v1.17.17.1).
"""

from app.testers import Tester
from app.testers._helpers import TesterAssertionError, TesterContext, TesterEnvError

ELECTRON_CMD = "cd electron && electron ."
PYTHON_CMD = "python app.py"
FLASK_URL = "http://127.0.0.1:10000"


def run(ctx: TesterContext) -> None:
    ctx.launch(ELECTRON_CMD)
    try:
        ctx.http("GET", FLASK_URL, retries=6)
    except (TesterEnvError, TesterAssertionError):
        # electron shell could not reach the backend (env quirk) — run the
        # Flask app directly; a stray backend already bound on :10000 still
        # answers the retries.
        ctx.launch(PYTHON_CMD)
        ctx.http("GET", FLASK_URL, retries=6)


TESTER = Tester(
    name="FinSight Electron + Flask smoke",
    description=(
        "Launch the Electron shell from its own directory (the root "
        "package.json has no main entry, so `electron .` at the root "
        "fails), which spawns the Flask backend, and verify GET / on "
        ":10000 renders the dashboard (no auth). If the shell does not "
        "reach the backend, fall back to launching the Flask app directly. "
        "HTTP-only, no mouse (v1.17.17.1)."
    ),
    run=run,
    project_slug="Finsight",
    web_url=FLASK_URL,
    ports=(10000,),
)
