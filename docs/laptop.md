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
whole migration is complete when `.\.venv\Scripts\python.exe run.py --check`
reports all startup checks ok and the dashboard answers at
`http://192.168.4.40:8000`.

> **venv never needs activating.** PowerShell's default execution policy blocks
> `Activate.ps1` on most machines, so every command below uses the venv's
> python explicitly (`.\.venv\Scripts\python.exe`) — the autostart task does
> the same (via `pythonw.exe`).

## One-time setup

```powershell
git clone https://github.com/jamesdileva/Sentinel.git   # or cd into existing clone + git pull
cd Sentinel

# Only a Python venv is required — the repo ships the built dashboard in
# backend/app/static, so no Node toolchain is needed on the laptop:
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e "backend[dev]"

# .env (gitignored) — from .env.example; defaults are safe, only these matter:
#   SENTINEL_OLLAMA_HOST=http://127.0.0.1:11434   (native Ollama, same host)
#   SENTINEL_GITHUB_TOKEN=<read-only PAT>         (repo auto-sync, Sprint 12.1)
```

(Optional) To rebuild the dashboard from the frontend sources you need Node:
`cd frontend; npm install; npm run build; cd ..` then
`.venv\Scripts\python.exe scripts\build.py --dist` — skip this if you never
touch the frontend.

**Start the server** (recommended): `.\.venv\Scripts\python.exe run.py` →
startup checks (SQLite, Ollama, frontend built) then uvicorn on
`127.0.0.1:8000`. For always-on runs from login:
`.\.venv\Scripts\python.exe scripts\install_service.py --install` registers a
`Sentinel` Task-Scheduler task that runs `run.py --service` every 5 minutes
(exits instantly if the port is already serving — the server itself runs 24/7,
the task only restarts it after crashes/reboots).

Repos are found under `SENTINEL_WATCH_DIRS`; it **defaults to the current
user's home directory** (`~`, i.e. `C:\Users\james` on this laptop), so you do
NOT need to set it — the repos just need to live under `~` (or set
`SENTINEL_WATCH_DIRS=C:\Users\james` in `.env` if you prefer an explicit
value). The `repo-sync` beat keeps GitHub checkouts current every 24 h
(`SENTINEL_SYNC_INTERVAL_MINUTES` — a sync also runs once at startup, and the
header "Sync now" button forces one immediately) and auto-queues knowledge
(RAG) indexing when Ollama is up. Since v1.17.6.6 the **security scan runs at
the end of each sync pass** (sync → knowledge index → security scan) — there
is no separate scan schedule anymore, so every project is scanned at least
once per 24 h cycle.

## v1.17.6.6 upgrade steps (one-time)

Markdown files are now chunked (2000 chars/overlap) and summaries are built
from docs-first context + recent commit messages — the stored vectors and
summaries were made with the old scheme, so re-generate them once:

```powershell
git pull
# stop the server if it runs (taskkill the run.py PID from `netstat -ano`)
.\.venv\Scripts\python.exe -m app.cli rag-index --reset   # inside backend\
.\.venv\Scripts\python.exe run.py                          # restart — auto-index re-embeds everything
```

Or use the Knowledge page: **Rebuild knowledge index**, then **Re-index all
projects** (v1.17.6.4). Expected runtime for the full rebuild of ~2.9k files
on this laptop: a few hours. After the first 24 h sync cycle, Portfolio
security cells flip from `pending` to `clean` automatically.

## Daily operations

```powershell
git pull                         # update the repo (includes the staged dashboard)
.\.venv\Scripts\python.exe run.py --service   # ensure it's running (the scheduler task does this)
..\.venv\Scripts\python.exe -m app.cli sync   # immediate repo sync if impatient (run from inside backend)
```

- Dashboard: `http://192.168.4.40:8000` · System page: `/system`
- **The staged dashboard ships inside the release commit** (`backend/app/static`
  is versioned, v1.16.2) — `git pull` alone updates the dashboard; you never
  need Node or a rebuild on this machine. Only if you changed `frontend/`
  locally do you run `scripts/build.py --dist` (from the repo root).
- If the Dashboard's "Live activity" panel is empty on load even though things
  are running: check `http://127.0.0.1:8000/api/v1/system/activity?limit=10`
  in the browser (rows = fine; `events:[]` + a `activity persist failed`
  WARNING in the server log = the SQLite writer is failing) — the panel
  re-seeds history on mount (v1.17.2).

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

- **RAG chat says "knowledge index is damaged on disk"** (503) → rebuild:
  the Knowledge page shows a "Rebuild knowledge index" button since v1.17.6.2
  (the earlier probe missed this damage), or from inside `backend`:
  `..\.venv\Scripts\python.exe -m app.cli rag-index --reset` — then restart
  `run.py` and the startup auto-index re-embeds everything, including the AI
  architecture summary (once per project, v1.17.6.2). Note: bare `sentinel`
  is never on PATH — always use the venv python by path.
- `frontend` changed but dashboard is stale → forgot `scripts/build.py --dist`;
  the backend serves the *staged* build from `backend/app/static`.
- Port 8000 already in use → another Sentinel is running (a second console
  left open is the usual cause). Since v1.17.6.3 `run.py` names the owner:
  it prints the PID (from `netstat -ano`) with a
  `taskkill /F /PID <pid>` hint instead of a raw bind traceback. Close the
  other console, kill that PID, or serve on another port
  (`.\.venv\Scripts\python.exe run.py --port 8100` + `SENTINEL_PORT=8100`
  in `.env`).
- "What happened this run?" → `data/logs/sentinel.log` (repo `data/logs/`).
  Overwritten at every start, INFO level, includes uvicorn's own logs —
  the place to look after a forced shutdown or an error cascade that
  scrolled past the console. Since v1.17.6.4 the `POST /api/embed` httpx
  flood is silenced (WARNING), so the file shows app + uvicorn activity
  only, each line exactly once.
- Projects indexed but the AI architecture summary is missing (files show
  embedded, no summary; v1.17.6.3 timeout or post-reset case) → **Re-index
  all projects** button on the Knowledge page (v1.17.6.4): incremental —
  already-embedded files are skipped, the missing summaries regenerate. The
  exact same pass from the console (from inside `backend`):
  `..\.venv\Scripts\python.exe -m app.cli rag-index --all`.
- Arch-summary generation "timed out" in the log → the client timeout was
  120 s and 4 concurrent embedding workers saturate Ollama at startup;
  v1.17.6.4 raises the default to 600 s (`SENTINEL_OLLAMA_TIMEOUT_SECONDS`
  overrides in `.env`). Summary still failed → run the re-index-all above,
  it backfills.
- After moving the repo folder on disk: the venv paths in the Task-Scheduler task
  are absolute — uninstall and re-install it (`scripts/install_service.py`).
- Portfolio security cell shows `⚠ pending` on every project right after an
  upgrade → not a bug since v1.17.6.6: "never scanned" is now distinct from
  "scanned and clean". Scans run chained to the daily repo-sync (or force one
  with `POST /api/v1/security/scan?project_id=` from the dashboard's Security
  page); the cell flips to `✓ clean` after the first scan with no findings.
