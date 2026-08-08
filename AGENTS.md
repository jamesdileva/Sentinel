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
| AI | Ollama (local); LLM `gemma2`, embedding `nomic-embed-text` |
| Task queue | Celery + Redis (Sprint 4+, Docker) |
| Watch dirs | `C:\Users\j` (configurable via `SENTINEL_WATCH_DIRS`) |

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

## Deployment (Sprint 12)

- **One compose file is the single source of truth** (`docker-compose.yml`):
  backend, frontend (nginx, served at `:8080`), worker, scheduler, redis,
  plus the optional `ollama`/`pihole` profiles. `docker-compose.dev.yml` holds
  dev overrides (source mount + reload) and is loaded **only** by
  `python scripts/dev.py` — a bare `docker compose up` on the laptop is prod.
- **Laptop (192.168.4.40) is the always-on home server**: runbook in
  docs/02 §13.4, dashboard at `http://192.168.4.40:8080` from any LAN device.
- **Env overrides**: `SENTINEL_OLLAMA_HOST`, `SENTINEL_GITHUB_TOKEN` +
  `SENTINEL_PROJECTS_DIR` (local clone target; repos auto-synced from GitHub
  by `repo-sync`, no SMB), `SENTINEL_PIHOLE_HOST`/`SENTINEL_PIHOLE_PASSWORD`
  (v6 session auth), `SENTINEL_API_PORT` — see `.env.example`.
- **System page**: `/system` is a read-only home snapshot (Ollama availability/
  models/tokens-per-sec + Pi-hole stats + startup checks). Per Rule 2 it never
  toggles anything server-side.
- **Release tooling**: `python scripts/release.py` → `dist/sentinel-<v>.zip` +
  `.sha256` (compose, Dockerfiles, nginx conf, `.env.example`, docs);
  `python scripts/build.py` builds both images (tests first unless
  `--skip-tests`).
- **Laptop operations**: `docs/laptop.md` is the on-server checklist (SMB map,
  compose commands, Pi-hole password, known issues); troubleshooting table in
  docs/02 §13.4. Never start Pi-hole from Docker Desktop's UI (resets the
  password), and never stop Docker wholesale on the laptop (Pi-hole is the
  network DNS).
