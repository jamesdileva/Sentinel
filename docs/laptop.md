# Laptop Deploy Checklist (192.168.4.40 — the always-on home server)

Quick reference for the laptop. Full runbook: `docs/02` §13.4 (Sprint 15 native
install — no Docker, no compose).

## Moving off Docker (one-time, run BEFORE the first native start)

DNS has already been moved back to **Automatic** on the router (eero app →
Custom DNS → Automatic) — Pi-hole is being removed completely and the network
falls back to the normal ISP DNS. Verify once: `nslookup doubleclick.net` now
returns a real IP, not `0.0.0.0`.

Then, on the laptop, still inside the **old** Sentinel checkout (before
`git pull` — that's the last moment the compose file exists):

```powershell
# 1. Stop the old Docker stack while the compose file is still present
docker compose down

# 2. Everything is leaving: images, volumes, containers (Pi-hole included).
#    Only safe now that DNS is back on Automatic — nothing on this machine
#    depends on a container anymore.
docker system prune -a --volumes -f

# 3. Docker Desktop itself can go too (the next sprint ships a desktop EXE,
#    not containers)
#    Windows: Settings > Apps > Installed apps > Docker Desktop > Uninstall

# 4. If an old "Sentinel" autostart task exists from a previous experiment:
schtasks /Delete /TN Sentinel /F        # ignore "not found"

# 5. Old runtime data from the container era (indexes are re-built from the
#    synced repos; safe to drop)
Remove-Item -Recurse -Force .\data
```

After the wipe, `git pull` and continue with the One-time setup below. The
whole migration is complete when `python run.py --check` reports all startup
checks ok and the dashboard answers at `http://192.168.4.40:8000`.

## One-time setup

```powershell
git clone https://github.com/jamesdileva/Sentinel.git   # or cd into existing clone + git pull
cd Sentinel

# Only a Python venv is required — the repo ships the built dashboard in
# backend/app/static, so no Node toolchain is needed on the laptop:
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# .env (gitignored) — from .env.example; defaults are safe, only these matter:
#   SENTINEL_OLLAMA_HOST=http://127.0.0.1:11434   (native Ollama, same host)
#   SENTINEL_GITHUB_TOKEN=<read-only PAT>         (repo auto-sync, Sprint 12.1)
```

(Optional) To rebuild the dashboard from the frontend sources you need Node:
`cd frontend; npm install; npm run build; cd ..` then
`.venv\Scripts\python.exe scripts\build.py --dist` — skip this if you never
touch the frontend.

**Start the server** (recommended): `python run.py` → startup checks (SQLite,
Ollama, frontend built) then uvicorn on `127.0.0.1:8000`. For always-on runs from
login: `python scripts/install_service.py --install` registers a `Sentinel`
Task-Scheduler task that runs `run.py --service` every 5 minutes (exits instantly
if the port is already serving — the server itself runs 24/7, the task only
restarts it after crashes/reboots).

Repos are found under `SENTINEL_WATCH_DIRS` (default `C:\Users\j`); the `repo-sync`
beat keeps GitHub checkouts current every 15 minutes (`SENTINEL_SYNC_INTERVAL_MINUTES`)
and auto-queues knowledge (RAG) indexing when Ollama is up.

## Daily operations

```powershell
git pull                         # update the repo (includes the staged dashboard)
python run.py --service          # ensure it's running (the scheduler task does this)
.venv\Scripts\python.exe -m app.cli sync   # immediate repo sync if impatient (run inside backend)
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
- Pi-hole is gone and the router DNS is back to Automatic — the laptop no
  longer controls the network's DNS.

## Known issues (see docs/02 §13.4 troubleshooting table)

- `frontend` changed but dashboard is stale → forgot `scripts/build.py --dist`;
  the backend serves the *staged* build from `backend/app/static`.
- Port 8000 already in use → another app is bound to it; `python run.py --port
  8100` (and set `SENTINEL_PORT=8100` in `.env`).
- After moving the repo folder on disk: the venv paths in the Task-Scheduler task
  are absolute — uninstall and re-install it (`scripts/install_service.py`).
