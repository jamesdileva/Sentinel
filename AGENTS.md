# AGENTS.md

> [!NOTE]
> Sentinel-wide working notes live at the top; newest entries at the bottom
> of the changelog unless otherwise dated.

## 2026-08-23 — Builds tab stuck "Working..." (orphaned BuildLog rows) + suite hang

- **Root cause (Surfhop, found live):** `POST /builds/run` creates the
  `BuildLog` row immediately, but the scheduler pool is 2 shared workers —
  a build queued behind knowledge indexing that loses the race against an
  app restart is discarded silently (`job_scheduler.shutdown(wait=False)`,
  no DB cleanup). The row keeps `completed_at IS NULL`; status derivation
  (`schemas/build.py`) reports any such row as "running" forever, and
  `Builds.tsx:86-93` resume-polling re-sticks "Working…" on every page
  load. No startup sweep existed for `BuildLog`.
- **Fix:** `BuildLogRepository.mark_orphaned_as_failed()` (exit_code=-1,
  success=False, "Aborted: Sentinel restarted...") wired into the lifespan
  in `main.py` next to the screenshot sweep; every restart now self-heals
  all projects. The stale Surfhop row was also healed directly in SQLite.
  Tests: `backend/tests/test_build_repository.py`.
- **Suite hang fixed en route:** the full backend suite dead-locked at ~20%
  in `test_all_registered_features_pass_against_fake_page` — Betsim's
  onboarding dismissal loops `while next.count(): click()` and the generic
  fake page's locator always reported count()==2. Electron features are now
  excluded from the generic sweep (own CDP launch contract, like native)
  with a dedicated `_BetsimPage` fake whose Next-count actually drains;
  Card-Game HiLo gets `_HiLoFriendlyPage` because role buttons must read
  enabled. Stale registry slug sets refreshed (`Betsim`, `Surfhop`).
- **Lint debt from parallel tester commits cleaned:** surfhop.py referenced
  undefined `GODOT_IMAGE_PREFIX` (F821 — would crash hold-window cleanup;
  ground truth `Godot_v*.exe` confirmed in surfhop/tools/godot.cmd), plus
  dead imports in surfhop/betsim and an unused `os` in main.py.
- **Known pre-existing debt:** pytest coverage gate reads 87.32% vs the
  90% fail-under (recent low-covered tester modules); everything else
  (pytest, black, isort, flake8 --max-line-length=100) is green.

## 2026-08-22 — Card-Game: full gameplay coverage (API + click-through)

- **Tier-1 (`testers/card_game.py`):** after the health checks the smoke now
  drives the real HTTP API end to end with a throwaway `api_tester_<ns>`
  account (httpx, cookie jar): register → login → invalid-bet 400 → spin →
  coinflip → highlow start+guess → open-crate basic → unknown-crate-type
  400. Asserts status codes and key JSON fields.
- **Features (`features/card_game.py`) grew from 1 to 4:** existing slots
  spin plus new Coin Flip round, Hi-Lo round, and BASIC crate opening
  (Store tab → reveal modal → Nice). Register+login extracted into a shared
  `_register_and_login(ctx)` helper.
- **Locator refresh after the app's HUD/tabs layout pass:** balance moved to
  a sticky HUD bar — features now use `[data-testid="balance"]` (the app
  added the hook for us) instead of the removed `div.text-xl.font-bold.mb-2`.
  Game switcher tabs are substring-matched by name (`Coin Flip`, `Hi-Lo`,
  `Store`); flip/spin buttons match `Flip $…` / `🎰 $…` via regex.
- **Two gotchas hit during the live E2E run:**
  1. The app's new auth validation rejects hyphens AND caps usernames at 20
     chars — throwaway names are `tester_<ns % 10^9>` /
     `api_tester_<ns % 10^9>` now.
  2. Features share one Playwright page: feature #1's dialog listener stays
     attached and double-dismisses feature #2's register alert ("Cannot
     dismiss dialog which is already handled"). `_on_dialog` is idempotent
     now (try/except around dismiss; the event flag is what counts).
- Verified live against dev servers (:5173/:3000): API block + all 4
  features pass with non-blank screenshots; flake8/black/isort clean;
  backend/tests/test_testers.py 40 passed. — Project Sentinel Rules for AI Agents

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
- Scripted testers live in `backend/app/testers/` (one module per app, registered by project slug in the `TESTERS` dict; see `docs/tier2_plan.md`)
- Error triage for failed sessions is deterministic-first (`docs/tier3_plan.md`): `POST /api/v1/sessions/{id}/triage` (evidence packet, no AI) + optional `.../summarize` (interpretation only)
- New-project integration tiers, live-verify checklist and verified ground-truth template: `docs/integration.md`
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
  `http://127.0.0.1:8420` (localhost only, Rule 1; v1.17.8.1 moved off 8000 so
  the dev servers of indexed projects — Cg, Demake Engine — can bind it).
  Ollama runs natively on the same machine (`http://127.0.0.1:11434`); Pi-hole
  remains an independent network DNS — **never start/stop it from Sentinel**
  (no code, no env).
- **GitHub is optional (v1.17.7)**: tokenless first-class — all projects live
  under `C:\Users\j\projects` (v1.17.7.3 moved them from home; the watch root
  is `SENTINEL_WATCH_DIRS=C:\Users\j\projects` in `.env`, with
  `projects\jamesdileva` and `projects\juduncan` canonical checkouts) and are
  indexed directly from disk; the `repo-sync` beat registers only when
  `SENTINEL_GITHUB_TOKEN` is set. The security scan-all runs on its own daily
  beat (`SENTINEL_SCAN_INTERVAL_MINUTES`) regardless of the token. Discovery
  prunes noise dirs (node_modules, .venv, ...), so the projects root scans
  cheaply — the home dir is no longer walked at all.
- **Indexing is git-tracked (v1.17.7.3)**: file lists come from
  `git ls-files` for git checkouts (fallback: the walk), so untracked `.env`
  secrets and junk never enter the index; `SENTINEL_WATCH_DIRS` accepts a
  single directory, comma-separated, or JSON. The world simulator is off by
  default (`SENTINEL_WORLD_SIM_ENABLED=true` re-enables it).
- **Env overrides**: `SENTINEL_OLLAMA_HOST`, `SENTINEL_GITHUB_TOKEN` (optional),
  `SENTINEL_GITHUB_EXCLUDE` (optional, comma-separated `owner/repo` list the
  repo-sync skips — v1.17.9.1), `SENTINEL_WATCH_DIRS`, `SENTINEL_PORT`,
  `SENTINEL_DB_PATH`/
  `SENTINEL_CHROMA_PATH`, `SENTINEL_SCAN_INTERVAL_MINUTES`,
  `SENTINEL_PORTFOLIO_DIR` (session-screenshot export target, default
  `projects\jamesdileva\jamesdileva.github.io` — v1.17.10) — see `.env.example`.
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
  server manually with `run.py` and keep port 8420 free of other services.
