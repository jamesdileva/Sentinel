# AGENTS.md

> [!NOTE]
> Sentinel-wide working notes live at the top; newest entries at the bottom
> of the changelog unless otherwise dated.

## 2026-10-08 — Audit Batch 1: RAG correctness (A1 stale vectors · A2 retry · A3 lock · A4 reset barrier)

- **A1 — deleted and re-chunked files left stale Chroma vectors.** The
  relational side always removed the row, but its vectors survived, so a
  deleted source stayed retrievable as "knowledge". Worse, and subtler: a
  Markdown file that shrinks from 10 chunks to 2 only overwrites `{row}#0`
  and `{row}#1` — `#2..#9` answered questions with superseded text forever.
  New `ChromaManager.rows_where`/`delete_where` make the metadata queryable;
  `_retract_obsolete_chunks` subtracts the freshly written ids from the
  stored set *for the same `file_path`* (so untouched files keep their
  current vectors), and `Indexer._index_files` retracts on delete.
  Gotcha worth remembering: Chroma's `get`/`delete` accept exactly one
  operator per `where`, so a two-key filter must be wrapped in `$and`.
- **A2 — embedding failure re-issued the identical request.** The
  `except: return self._embed(text)` fallback ran the real embedder a second
  time, doubling an 1800 s Ollama timeout into an apparent hang. Failures now
  raise. `_embed_legacy` also wraps its httpx errors so the legacy endpoint
  honours the same error contract as `/api/embed`.
- **A3 — knowledge indexing had no per-project mutual exclusion.** Startup
  auto-index, repo sync, `/rag/index`, `/rag/index/all` and the CLI could all
  queue the same project: two workers read the same pending files, embedded
  the same content twice and raced `embedding_id`. New
  `services/knowledge_coordinator.py` holds a per-project `RLock`
  (`knowledge_lock`) for the whole run in all three entry points.
  Process-local on purpose — the races live in run.py's own thread pool
  (Rule 8: no filesystem lock yet).
- **A4 — reset raced an in-flight index.** `run_reset_knowledge` cancelled
  *queued* jobs but let running ones finish, so the job it was trying to stop
  wrote its vectors straight back into the collections the reset had just
  wiped. A process-local generation counter now invalidates in-flight runs
  (`assert_current` guards `ingest_files` and every phase boundary in
  `index_project`), and reset holds all project locks across the wipe.
  Found while testing: the wipe must be unconditional — an empty database
  still means the shared collections on disk have to go.
- **Tests:** +11. Five consecutive full-suite green runs (512 tests);
  `flake8 --max-line-length=100` + `black` clean.
- **Known pre-existing flake (not from this change, verified on a clean
  tree):** `test_query_all_projects_is_summary_first` and
  `test_rag_query_persists_assistant_reply` can fail when
  `test_rag_api.py` and `test_rag_service.py` run together (shared
  Chroma/settings state between the two files). The full suite is
  consistently green.

## 2026-10-08 — Summaries move to qwen3.5:9b; chat keeps llama3.1:8b

- **Trigger:** a blind head-to-head on the *real* architecture-summary path
  (`scripts/eval_summary_head_to_head.py --project sentinel --max-tokens
  2500 --think off`, 1 run/model, same 35776-char docs-first prompt,
  num_ctx 14937). Judgment on `BLIND_A/B.md` before reading `MAPPING.txt`,
  then claim-checked against this checkout.
- **Result:** qwen3.5:9b wrote the better summary — 4 grouped domains with
  real paths (`backend/app/main.py`, `apscheduler`), the React/TS frontend,
  SQLite + ChromaDB named explicitly, exact build commands
  (`pip install -e "backend[dev]"`, `scripts/build.py --dist --desktop`,
  `127.0.0.1:8420`) and the Tier 1/2/3 testing taxonomy. llama3.1:8b listed
  15 flat components of mixed granularity, never mentioned the frontend or
  either data store, answered the build workflow with vague prose, and
  duplicated 4 milestones verbatim (a self-repetition loop that would embed
  into ChromaDB and pollute retrieval).
- **Speed is the trade:** qwen 1.6 tok/s vs llama 2.9 tok/s on the same
  hardware (~1.8x). Wall time was ~equal (741s vs 734s) because the
  12k-token prefill dominates both. Summaries are background work, chat is
  interactive — hence the split rather than a wholesale swap.
- **Split:** new `SENTINEL_OLLAMA_SUMMARY_MODEL` (default `qwen3.5:9b`)
  reaches `ingest_project_summary` via a new `model=` parameter on
  `RagService._generate_with_metrics`. Chat answers, the `/system`
  `model_default`, and the empty-context fallback still use
  `SENTINEL_OLLAMA_MODEL`. `KnowledgeSummary.model` now records the model
  that actually wrote each summary (old rows keep their provenance until
  regenerated).
- **Also fixed en route (investigating the empty-output run):**
  `OllamaService.generate_with_metrics` now passes through Ollama's
  `thinking` / `done_reason` / `prompt_eval_count` (previously discarded),
  which is what made the earlier qwen run unfalsifiable: 1250 tokens spent
  entirely on the hidden reasoning chain, `response=""`, and no way to see
  it. A `think=False` flag was added for answer-only comparisons.
  `generate()`/`generate_with_metrics()` also thread it through.
- **Eval tooling** (`scripts/eval_summary_head_to_head.py` — the model
  shootout, and `scripts/eval_embedding_retrieval.py` — the embedding probe
  that settled the "bigger embedder?" question): unknown model tags are a
  hard error instead of a warning that fails 20 minutes in; `results.json`
  is written in a `finally` so an aborted run still reports partial results
  (a previous crash left only bare `.md` files); per-trial `<label>.json` +
  `<label>_thinking.md`; headers carry `done_reason` and `think`.
- **Verification:** 501 backend tests green (including a new
  summary-vs-chat model/cap assertion and 3 Settings/warning cases), 116
  frontend, `flake8 --max-line-length=100` + `black` clean, `tsc --noEmit`
  clean. `/system` and the Settings page expose both models with a
  dedicated validation warning when the summary tag is not installed.
- **Note for the user:** live summaries only switch once a project is
  re-indexed (`--summary` or the missing-summary backfill); the 29 stored
  summaries keep saying `llama3.1:8b` until then.
- **Embedding bakeoff verdict (do NOT switch):** the retrieval probe on the
  full Sentinel corpus (467 chunks, 20 ground-truth questions) showed
  nomic-embed-text has the best hit@5 (0.65 vs 0.60/0.60/0.55), is 1.7-6x
  the fastest (5.4 docs/s) and smallest (274MB); bge-m3/qwen3-embedding won
  hit@1 by 3 questions, which is inside the noise at n=20. The real signal
  was that *every* model missed ~40% of questions — a retrieval-pipeline
  problem, confirmed by audit_new.md's RAG recommendations.

## 2026-09-12 — Frozen exe saw empty data (per-machine store vs repo dataset)

- **Root cause:** the packaged shell forced `SENTINEL_DB_PATH/...` into
  `%APPDATA%\Sentinel\data` (fresh 0-project DB) and never read the repo
  `.env`, so the exe showed no projects, no knowledge, and wrong watch
  dirs while terminal `run.py` showed all 29 projects. Repo data was never
  at risk — just invisible to the exe.
- **Fix (`962334c`):** `desktop/main.js` `repoDataDir()` — when the shell
  sees a checkout with `data/sqlite/sentinel.db`, the frozen server uses
  that repo `data/` (one shared dataset); Roaming stays the fallback for
  repo-less machines. `server_entry.py` loads the checkout `.env`
  (watch dirs, token, Ollama host) with shell-set vars winning. Backup of
  `data/sqlite` + `data/chroma` taken first
  (`data/backups/pre-exe-data-fix-*`, git-ignored).
- **To reach the installed exe:** rebuild + reinstall (`scripts/build.py`,
  then `npm run dist` in `desktop/`) — code-only change until then.
  Shell already attaches to a healthy `:8420` backend, so terminal + exe
  can't double-write the DB.
- **Also:** `docs/integration.md` Velocity lessons refreshed (buildlog
  sweep, tester gates, both-registry import gate) for propagation to the
  integrated projects.

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
