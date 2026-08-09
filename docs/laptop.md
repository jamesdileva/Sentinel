# Laptop Deploy Checklist (192.168.4.40 — the always-on home server)

Quick reference for the laptop. Full runbook: `docs/02` §13.4 (Sprint 15 native
install — no Docker, no compose).

## One-time setup

```powershell
git clone https://github.com/jamesdileva/Sentinel.git   # or cd into existing clone + git pull
cd Sentinel

# Only the venv, Node (one-time), and .env are needed:
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
cd frontend; npm install; npm run build    # → ../dist frontend build
cd ..
# build the dashboard into the backend (served from backend/app/static):
.venv\Scripts\python.exe scripts\build.py --dist   # verify + lint + build + stage

# .env (gitignored) — from .env.example; defaults are safe, only these matter:
#   SENTINEL_OLLAMA_HOST=http://192.168.4.40:11434   (native Ollama, same host)
#   SENTINEL_DB_PATH=C:\Sentinel\data\sqlite\sentinel.db   (default is fine)
```

The laptop binds only `127.0.0.1` (dashboard and API on `http://192.168.4.40:8000`;
Pi-hole remains the LAN DNS as before — it is NOT part of Sentinel's stack).

**Start the server** (recommended): `python run.py` → startup checks (SQLite,
Ollama, frontend built) then uvicorn on `127.0.0.1:8000`. For always-on runs from
login: `python scripts/install_service.py --install` registers a `Sentinel`
Task-Scheduler task that runs `run.py --service` every 5 minutes (exits instantly
if the port is already serving).

Repos are found under `SENTINEL_WATCH_DIRS` (default `C:\Users\j`); the `repo-sync`
beat keeps GitHub checkouts current every 15 minutes (`SENTINEL_SYNC_INTERVAL_MINUTES`)
and auto-queues knowledge (RAG) indexing when Ollama is up.

## Daily operations

```powershell
git pull                         # update the repo
.venv\Scripts\python.exe scripts\build.py --dist   # re-verify + rebuild dashboard
python run.py --service          # ensure it's running (the scheduler task does this)
.venv\Scripts\python.exe -m app.cli sync              # immediate repo sync if impatient
```

- Dashboard: `http://192.168.4.40:8000` · System page: `/system`

## Rules of thumb

- **Never move the `data/` directory** while the server runs — it holds
  `sqlite/sentinel.db`, `chroma/`, and `world_sim/`. If you do relocate, re-run
  `sentinel index --all` once.
- No Docker, no nginx, no reverse proxy — one uvicorn process serves API +
  dashboard (http://127.0.0.1:8000). Keep that port for Sentinel.
- Ollama runs natively on the laptop (`OLLAMA_HOST=0.0.0.0:11434` set once via
  `setx`, then restart the Ollama tray app).

## Known issues (see docs/02 §13.4 troubleshooting table)

- `frontend` changed but dashboard is stale → forgot `scripts/build.py --dist`;
  the backend serves the *staged* build from `backend/app/static`.
- Port 8000 already in use → another app is bound to it; `python run.py --port
  8100` (and set `SENTINEL_PORT=8100` in `.env`).
- After moving the repo folder on disk: the venv paths in the Task-Scheduler task
  are absolute — uninstall and re-install it (`scripts/install_service.py`).