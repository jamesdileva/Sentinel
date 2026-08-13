# AGENTS.md — Project Sentinel Rules for AI Agents

These are the project's constitution. They must be upheld in every decision, change, and commit.

## The 8 Project Rules (docs/01 §5)

1. **Everything stays local.** Data never leaves the device unless explicitly exported by the user.
2. **AI is assistive, never autonomous.** AI generates summaries, explanations, and search results. It never executes irreversible actions.
3. **Determinism over generation.** Known workflows (builds, tests, scans) are deterministic. AI is used only for interpretation.
4. **One responsibility per module.** Each component does exactly one thing well.
5. **Projects are known entities.** Sentinel indexes known repositories, not arbitrary web apps.
6. **Every feature must be testable.** No feature ships without unit or integration tests.
7. **Transparency over opacity.** All decisions are traceable and explainable.
8. **Simplicity over optimization.** Prefer readable, maintainable code over premature optimization.

## Agent Development Guidelines (docs/01 §16)

1. Always prefer deterministic logic over AI for anything involving correctness or security.
2. Document every AI-generated summary with clear provenance metadata (model, timestamp).
3. Keep changes modular — one responsibility per module/service/component.
4. Write tests for every new endpoint, service method, and utility function.
5. Run all existing tests before committing (`pytest` in `backend/`).
6. Follow formatting standards: `black`, `isort`, `flake8` for Python; `prettier` + `eslint` for TS.
7. Update relevant docs when modifying architecture or APIs.

## Architecture Decisions (locked in Sprint 0)

| Decision | Choice |
|----------|--------|
| Primary database | **SQLite** (file-based, `/data/sqlite/sentinel.db`) — not PostgreSQL |
| Vector database | **ChromaDB embedded** (python client, persistent dir) — no container |
| Backend ORM | SQLModel (SQLAlchemy 2.0 base) |
| Backend framework | FastAPI, Pydantic v2 |
| Frontend | React 19+, TypeScript, Vite, TailwindCSS |
| AI | Ollama (local); LLM `llama3.1:8b` (since v1.17.6.5; won the head-to-head vs gemma2), embedding `nomic-embed-text` |
| Task queue | In-process APScheduler + thread pool (no Redis/Celery — Sprint 15 removed the deferred Docker queue) |
| Watch dirs | Current user's home (`Path.home()`, configurable via `SENTINEL_WATCH_DIRS`) |

## Source of Truth

- `docs/01_Master_Architecture.md` — architecture (read before designing)
- `docs/02_Implementation_Guide.md` — schemas, API contracts, service interfaces
- `docs/03_Sprint_Plan.md` — active sprint and acceptance criteria

## Conventions

- Pydantic response schemas live in `backend/app/schemas/` (not `models/`)
- Language parsers live in `backend/app/parsers/`
- All tests live in `backend/tests/`
- API routes are versioned: `/api/v1/...`
- Status/read endpoints use GET; state-changing actions use POST
- Never commit secrets, `.env`, or `data/` content (see `.gitignore`)

## Deployment (Sprint 12 → 15: native install, no containers)

- **The project runs natively**: one uvicorn process serves the API + built
  dashboard from the same origin (`backend/app/static`).
  `.\.venv\Scripts\python.exe run.py` is the single starting point (startup
  checks: SQLite, Ollama, frontend built; **no venv activation needed — the
  venv python is called by path everywhere**; the venv is `backend\.venv` on
  this machine, the repo-root `.venv` elsewhere).
  The server is started manually (no autostart task — v1.17.7.2 removed
  `scripts/install_service.py`: the 5-min Task-Scheduler rerun popped console
  windows every time it spawned the server).
  `scripts/build.py --dist` verifies (backend pytest + lint, frontend test +
  build) and stages the dashboard; `scripts/release.py` ships
  `dist/sentinel-<v>.zip` + `.sha256` (run.py, scripts, `.env.example`, docs,
  `backend/app`).
- **The desktop (this machine) is the single always-on server** (laptop retired
  since v1.17.7): runbook in docs/02 §13.4 and `docs/desktop.md`, dashboard at
  `http://127.0.0.1:8000` (localhost only, Rule 1). Ollama runs natively on the
  same machine (`http://127.0.0.1:11434`); Pi-hole remains an independent
  network DNS — **never start/stop it from Sentinel** (no code, no env).
- **GitHub is optional (v1.17.7)**: tokenless first-class — all projects live
  under `C:\Users\j` (the default watch dir, `Path.home()`, plus
  `C:\Users\j\jamesdileva` and `C:\Users\j\juduncan` canonical checkouts) and
  are indexed directly from disk; the `repo-sync` beat registers only when
  `SENTINEL_GITHUB_TOKEN` is set. The security scan-all runs on its own daily
  beat (`SENTINEL_SCAN_INTERVAL_MINUTES`) regardless of the token. Discovery
  prunes noise dirs (AppData, OneDrive, node_modules, .venv, ...), so the home
  dir with its non-project folders scans cheaply.
- **Env overrides**: `SENTINEL_OLLAMA_HOST`, `SENTINEL_GITHUB_TOKEN` (optional),
  `SENTINEL_WATCH_DIRS`, `SENTINEL_PORT`, `SENTINEL_DB_PATH`/
  `SENTINEL_CHROMA_PATH`, `SENTINEL_SCAN_INTERVAL_MINUTES` — see `.env.example`.
- **System page**: `/system` is a read-only home snapshot (Ollama availability/
  models/tokens-per-sec + startup checks). Per Rule 2 it never toggles
  anything server-side.
- **Release tooling**: `.\.venv\Scripts\python.exe scripts\release.py` →
  `dist/sentinel-<v>.zip` + `.sha256` (run.py, scripts/build.py, `.env.example`,
  docs, `backend/app`);
  `.\.venv\Scripts\python.exe scripts\build.py --dist` verifies and stages.
- **Machine operations**: `docs/desktop.md` is the on-server checklist (venv
  setup, build/stage, manual start, known issues); troubleshooting table in
  docs/02 §13.4. The venv lives at `backend\.venv` on this machine (or the
  repo-root `.venv`). There is no autostart task since v1.17.7.2 — start the
  server manually with `run.py` and keep port 8000 free of other services.
