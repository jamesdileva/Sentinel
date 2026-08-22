# Desktop Deploy Checklist (the always-on machine — localhost only)

Quick reference for this desktop (the single always-on machine since v1.17.7;
the laptop is retired). Full runbook: `docs/02` §13.4 (Sprint 15 native install
— no Docker, no compose).

> **venv never needs activating.** PowerShell's default execution policy blocks
> `Activate.ps1` on most machines, so every command below uses the venv's
> python explicitly (`backend\.venv\Scripts\python.exe` here — the repo-root
> `.venv` on other machines).

## Quick reference

| Task | Command (repo root unless noted) |
|---|---|
| Start / restart the server | `backend\.venv\Scripts\python.exe run.py` |
| …or just use the app | `desktop\dist\win-unpacked\Sentinel.exe` |
| Update everything | `git pull` → restart server (or relaunch the app) |
| Backup + off-disk copy | `backend\.venv\Scripts\python.exe -m app.cli backup --push D:\safe-place` *(from inside backend)* |
| Restore after a crash | see **Crash recovery** below |
| Verify + stage dashboard & frozen backend | `backend\.venv\Scripts\python.exe scripts\build.py --dist` |
| Rebuild desktop installer too | `...\scripts\build.py --dist --desktop` → `desktop\dist\` |
| Repo sync now / RAG reindex / knowledge reset | `sentinel sync`, `sentinel rag-index --all`, `sentinel rag-index --reset` *(CLI: `-m app.cli <cmd>` from inside backend)* |

## One-time setup

```powershell
git clone https://github.com/jamesdileva/Sentinel.git   # or cd into existing clone + git pull
cd Sentinel

# Only a Python venv is required — the repo ships the built dashboard in
# backend/app/static, so no Node toolchain is needed on this machine:
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"   # or .\.venv\... if the venv is at the repo root

# .env (gitignored) — from .env.example; defaults are safe, nothing is required:
#   SENTINEL_OLLAMA_HOST=http://127.0.0.1:11434   (native Ollama, same host — the default)
#   SENTINEL_GITHUB_TOKEN=<read-only PAT>         (OPTIONAL — repo auto-sync, Sprint 12.1; tokenless is first-class since v1.17.7)
#   SENTINEL_GITHUB_EXCLUDE=juduncan/cse455       (OPTIONAL — repos sync must skip, v1.17.9.1; this one cannot be deleted upstream)
```

(Optional) To rebuild the dashboard from the frontend sources you need Node:
`cd frontend; npm install; npm run build; cd ..` then
`backend\.venv\Scripts\python.exe scripts\build.py --dist` — skip this if you
never touch the frontend.

**Start the server**: `backend\.venv\Scripts\python.exe run.py` → startup
checks (SQLite, Ollama, frontend built) then uvicorn on `127.0.0.1:8420`
(localhost only — nothing is exposed on the LAN; v1.17.8.1 moved Sentinel off
8000 so the dev servers of indexed projects — Cg, Demake Engine — can bind
uvicorn's default 8000). There is **no autostart
task** (v1.17.7.2 removed `scripts/install_service.py`): the old 5-minute
Task-Scheduler rerun kept popping console windows every time it spawned the
server, and the server is run manually now.

Repos are found under `SENTINEL_WATCH_DIRS`. Since v1.17.7.3 this machine
sets it explicitly: `SENTINEL_WATCH_DIRS=C:\Users\j\projects` in `.env` — all
projects live there directly (v1.17.7.3 moved them from `C:\Users\j`; see
`scripts/migrate_projects_root.py`), so the home dir with its non-project
folders is never walked. The default (when unset) remains the current user's
home directory.
Since v1.17.7 GitHub is optional: with **no token** the local checkouts are
indexed straight from the watch dirs and the `repo-sync` beat isn't registered;
with a token the beat keeps GitHub checkouts current every 24 h
(`SENTINEL_SYNC_INTERVAL_MINUTES` — a sync also runs once at startup, and the
header "Sync now" button forces one immediately). **Security scans** run on
their own daily beat (`SENTINEL_SCAN_INTERVAL_MINUTES`, default 1440) since
v1.17.7 — independent of the sync — so every project is scanned at least once
per 24 h cycle even tokenless. Indexing auto-queues knowledge (RAG) jobs when
Ollama is up.

## Daily operations

```powershell
git pull                         # update the repo (includes the staged dashboard)
backend\.venv\Scripts\python.exe run.py                # start / restart the server
backend\.venv\Scripts\python.exe -m app.cli sync   # immediate repo sync if impatient (run from inside backend)
```

### Desktop shell (v1.17.18.6 — no more console)

`desktop/dist/win-unpacked/Sentinel.exe` is an Electron shell around the
same server (built with `npm run dist` inside `desktop/`). On launch it:

- **attaches** to a backend already serving on `127.0.0.1:8420`, or
- **spawns one** via `run.py` through the project venv (hidden window — no
  console ever appears), waits for `/health`, then opens the dashboard.

Quitting the window stops only a backend *this shell spawned*; an externally
started server keeps running. It finds the checkout by walking up from its
own location (works from `desktop\dist\win-unpacked\` inside a clone) or set
`SENTINEL_ROOT`. A second launch just refocuses the first window.

### Desktop shell + installer (Phase 2 packaging, v1.17.18.6)

`desktop/dist/` holds both artifacts (built with `npm run dist` inside
`desktop/`):

- `win-unpacked\Sentinel.exe` — portable launcher
- `Sentinel Setup <version>.exe` — per-user installer (Start Menu shortcut)

Since Phase 2 the **backend ships frozen inside the installer**
(PyInstaller onedir under `resources\server-runtime\`), so a machine needs
no repo, no venv, and no Python — install, click Sentinel. On first run it
spawns the bundled server and stores state under
`%APPDATA%\Sentinel\data\` (SQLite, Chroma, screenshots). Restore a backup
zip into that folder after a crash (see Crash recovery).

Development checkouts still prefer the repo venv (`run.py` flow above) when
the shell runs unpackaged; `SENTINEL_PORT` / `SENTINEL_ROOT` env vars work
in both modes.

- Dashboard: `http://127.0.0.1:8420` · System page: `/system`
- **The staged dashboard ships inside the release commit** (`backend/app/static`
  is versioned, v1.16.2) — `git pull` alone updates the dashboard; you never
  need Node or a rebuild on this machine. Only if you changed `frontend/`
  locally do you run `scripts/build.py --dist` (from the repo root).
- If the Dashboard's "Live activity" panel is empty on load even though things
  are running: check `http://127.0.0.1:8420/api/v1/system/activity?limit=10`
  in the browser (rows = fine; `events:[]` + a `activity persist failed`
  WARNING in the server log = the SQLite writer is failing) — the panel
  re-seeds history on mount (v1.17.2).

## Crash recovery (new machine / dead disk)

The backup zip (`sentinel backup --push D:\somewhere-safe` from inside
`backend`, or `scripts\backup.py --push`) contains **the fully indexed state**
— SQLite (projects, sessions, scores, findings, chat, summaries) + the Chroma
vectors + screenshots. Restoring it does NOT require re-indexing or
re-embedding: embedding ids in the restored DB point at the restored vectors.

```powershell
git clone https://github.com/jamesdileva/Sentinel.git; cd Sentinel
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
# restore the newest backup zip's contents into .\data\  (sqlite\, chroma\,
#   screenshots\ land exactly where they were)
backend\.venv\Scripts\python.exe run.py
```

Not covered by the zip — reinstall on a fresh machine:
- **Ollama** + model pull (`ollama pull llama3.1:8b nomic-embed-text`)
- Anything that changed *after* the last backup is picked up incrementally on
  the next scan/knowledge pass (edited files re-embed automatically).
- The projects themselves live outside `data/` as git checkouts under
  `SENTINEL_WATCH_DIRS` — clone/pull them as usual.

## Rules of thumb

- **Never move the `data/` directory** while the server runs — it holds
  `sqlite/sentinel.db`, `chroma/`, and `world_sim/`. If you do relocate, re-run
  `sentinel index --all` once.
- No Docker, no nginx, no reverse proxy — one uvicorn process serves API +
  dashboard (http://127.0.0.1:8420). Keep that port for Sentinel (indexed
  projects' dev servers use 8000, which is why Sentinel moved off it).
- Ollama runs natively on this machine (`http://127.0.0.1:11434`) — a localhost
  URL, never exposed (the laptop's `OLLAMA_HOST=0.0.0.0` setup is retired).
- Pi-hole is gone and the router DNS is back to Automatic — Sentinel never
  controlled it; the laptop no longer hosts anything for this project.
- **Desktop-app testers drive the real mouse/keyboard** (v1.17.18.5, audit2
  S10 warning): AG / Airadio / HFT features inject real `SendInput` events
  into the app's focused window. While such a tester runs, typing or moving
  the mouse can steal focus and inject keystrokes into *your* session —
  hands off until the run finishes (the runner refuses windows whose title
  doesn't match the project, but your own focus is yours to lose).

## Known issues (see docs/02 §13.4 troubleshooting table)

- **RAG chat says "knowledge index is damaged on disk"** (503) → rebuild:
  the Knowledge page shows a "Rebuild knowledge index" button since v1.17.6.2
  (the earlier probe missed this damage), or from inside `backend`:
  `backend\.venv\Scripts\python.exe -m app.cli rag-index --reset` — then
  restart `run.py` and the startup auto-index re-embeds everything, including
  the AI architecture summary (once per project, v1.17.6.2). Note: bare
  `sentinel` is never on PATH — always use the venv python by path.
- `frontend` changed but dashboard is stale → forgot `scripts/build.py --dist`;
  the backend serves the *staged* build from `backend/app/static`.
- Port 8420 already in use → another Sentinel is running (a second console
  left open is the usual cause). Since v1.17.6.3 `run.py` names the owner:
  it prints the PID (from `netstat -ano`) with a
  `taskkill /F /PID <pid>` hint instead of a raw bind traceback. Close the
  other console, kill that PID, or serve on another port
  (`backend\.venv\Scripts\python.exe run.py --port 8100` +
  `SENTINEL_PORT=8100` in `.env`).
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
  `backend\.venv\Scripts\python.exe -m app.cli rag-index --all`.
- Arch-summary generation "timed out" in the log → the client timeout was
  120 s and 4 concurrent embedding workers saturate Ollama at startup;
  v1.17.6.4 raises the default to 600 s, v1.17.6.8 to **1800 s** (the
  v1.17.6.6 doc-first summary prompt alone is a ~10k-token prefill that can
  outgrow 600 s mid re-index). `SENTINEL_OLLAMA_TIMEOUT_SECONDS` overrides in
  `.env`. Summary still failed → run the re-index-all above, it backfills.
  Since v1.17.6.8 summaries generate up to **1250 tokens**
  (`SENTINEL_OLLAMA_SUMMARY_MAX_TOKENS`) instead of the shared 500.
- Need a full re-embed (new chunking/summary prompt, e.g. right after an
  upgrade)? Since v1.17.6.8 the Knowledge page always shows **Rebuild
  knowledge index** (was hidden behind the damaged-index banner) → then
  **Re-index all projects**. Or from the console (from inside `backend`):
  `backend\.venv\Scripts\python.exe -m app.cli rag-index --reset` and
  restart — the startup auto-index re-embeds.
- After moving the repo folder on disk: nothing to re-register — there is no
  autostart task anymore (v1.17.7.2); just start `run.py` from the new
  location.
- Portfolio security cell shows `⚠ pending` on every project right after an
  upgrade → not a bug since v1.17.6.6: "never scanned" is now distinct from
  "scanned and clean". Scans run on their own daily beat since v1.17.7
  (`SENTINEL_SCAN_INTERVAL_MINUTES` — tokenless installs included; or force
  one with `POST /api/v1/security/scan?project_id=` from the dashboard's
  Security page); the cell flips to `✓ clean` after the first scan with no
  findings.