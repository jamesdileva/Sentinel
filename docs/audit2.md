# Sentinel Full Code-Quality Audit (audit2) — 2026-08-21

A whole-codebase quality pass over `backend/app` (~100 modules), the React
frontend, and the repo scripts, at v1.17.18.2. This is a **code** audit — it
deliberately excludes the operational findings already recorded in
`docs/audit.md` (backup path, log/screenshot growth, orphan processes,
dead `SENTINEL_API_KEY`, B1–B6), except where the current code contradicts a
claimed fix.

Method: five parallel deep-read passes (API/core, services,
db/repositories/schemas, parsers/testers/utils/scripts, frontend), every
finding verified against source with file:line evidence; plus a baseline run
of the test suite.

Priorities: **P0** = fix immediately · **P1** = fix in next batch ·
**P2** = track / fix opportunistically · **P3** = trivia.

> **Fix status (v1.17.18.3):** the entire top batch is applied —
> Q1, Q2, Q3, Q8, Q9 (all P1s) plus S1, Q6 and C2 from the P2 list.
> Items marked **[FIXED]** below; verification at the bottom of this file.
> Backend: 648 tests pass, flake8/black/isort clean.
> Frontend: 131 tests pass (18 files).

**Baseline health:** all backend tests pass, coverage gate met (90.03% ≥ 90).
Frontend has component tests for every page. No P0 found anywhere.

---

## P0 — none

---

## P1 — fix in next batch

### Q1. `run.py` checks `SENTINEL_PORT` but binds `args.port` (bind mismatch) — **[FIXED v1.17.18.3]**
`run.py:183` resolves `port = int(os.environ.get("SENTINEL_PORT", str(args.port)))`
and uses it for the occupancy probe — but `start_server(args)` (line 151–161)
passes `"--port", str(args.port)` to uvicorn. With `SENTINEL_PORT=9000` set
(it's a documented override in `.env.example`) and no CLI flag: the probe
tests 9000 while uvicorn binds 8420 → duplicate-instance detection is wrong.
The help text at `run.py:16` also implies CLI wins when env actually wins.
**Fix:** thread the resolved port through `start_server(args, port)`.

### Q2. A4 follow-through gap: launcher kill still skipped if `service.end()` throws — **[FIXED v1.17.18.3]**
`tester_runner.py:128-133`. The v1.17.18.1 audit-A4 fix put *both* statements
in one `finally`:
```python
finally:
    service.end(app_session.id, outcome, status)
    if launcher is not None:
        _kill_tree_best_effort(launcher)
```
If `end()` raises, `_kill_tree_best_effort` never runs — exactly the orphan
scenario A4 claimed to close — and the exception raised inside `finally`
masks the original error. **Fix:** kill first, wrapped in its own
try/except, then call `end()` in a second try/except.
Related latent crash: initial `status = "unknown"` (`tester_runner.py:109-110`)
reaches `SessionStatus(status)` (`app_sessions.py:225`) if a BaseException
interrupts the try block → unhandled `ValueError`. Initialize to a legal
terminal value (`"investigate"`).

### Q3. Dead exception hierarchy → inconsistent status codes for identical failures — **[FIXED v1.17.18.3]**
`core/exceptions.py` was designed as the central error→status dispatcher but
is never wired into FastAPI. Result: Ollama-unavailable maps to **503** in
`sessions.py:167-177` but escapes as an unhandled **500** from
`/rag/search` and `/rag/query` (`api/v1/rag.py:44-85`). There are also two
competing `OllamaUnavailableError` classes. **Fix:** one central
`@app.exception_handler(SentinelError)` mapping domain errors to statuses;
delete/merge the duplicates. Fixes the rag 500s and prevents future drift.

### Q4. No indexes on any foreign-key / filtered column — **[FIXED v1.17.18.3]**
Zero `index=True` in `backend/app` (`models.py` FK columns: lines 66, 83, 97,
115, 131, 147, 165, 219, 299, 318, 334, 354). Every repository filters on
`project_id`; session children on `session_id`; activity events order by
`created_at`. SQLite does **not** auto-index FK columns, so each lookup is a
full-table scan — `projectfile` grows to tens of thousands of rows.
**Fix:** add `index=True` on hot columns + migration entries (see Q5).

### Q5. Migration story is a hand-maintained ALTER list with no drift detection — **[FIXED v1.17.18.3]** (drift detection + index backfill added; Alembic-lite still open)
`connection.py:64-72,101-108`: `create_all` cannot add columns to existing
tables, so every future column addition must be manually appended to
`_MIGRATIONS` (3 entries so far; this already bit once — v1.17.1
wrong-table-name bug documented at lines 54-57). The world DB
(`world_sim_models.py:93-104`) has no migration path at all.
**Fix:** add a startup drift check (inspector columns vs model metadata →
fail loudly) at minimum; consider Alembic-lite or generated ALTERs later.

### Q6. Unbounded full-table load on hot endpoints (`OllamaQueryLog`) — **[FIXED v1.17.18.3]** (SQL `ORDER BY ... LIMIT`; retention prune still open)
`system_service.py:100-109`: `select(OllamaQueryLog)` with no ORDER BY /
LIMIT materializes *every logged generation ever*, sorts in Python, slices
to ~20. Runs on `/system/overview` and `/system/ollama` (dashboard home),
and the table grows forever (no prune exists anywhere — extends prior-audit B3).
**Fix:** `ORDER BY created_at DESC LIMIT n` in SQL + a retention prune like
`activity_bus.py:77-82`.

### Q7. `sql_parser` truncates CREATE TABLE bodies at the first `)`
`parsers/sql_parser.py:8-11`: `_CREATE_TABLE_RE` captures `(.*?)\)` —
non-greedy up to the **first** closing paren. Any column typed
`VARCHAR(255)` / `DECIMAL(10,2)`, any `CHECK (...)`, or composite PK ends
the capture early; all subsequent columns are silently missing from the
index structure. Verified against the regex directly. **Fix:** balanced-paren
scan of the body, or adopt sqlglot (Rule 3: deterministic parse).

### Q8. Release archive ships stale bytecode — **[FIXED v1.17.18.3]**
`scripts/release.py:48-56`: `_collect_files()` rglobs `backend/app` with no
exclusions; verified `__pycache__/*.pyc` files exist under parsers/, testers/,
utils/. Every `sentinel-<v>.zip` + `.sha256` includes compiled modules whose
import could win over source on timestamp skew. **Fix:** exclude
`__pycache__`/`*.pyc` in `_collect_files`.

### Q9. Frontend: transient fetch failure permanently latches `error` — **[FIXED v1.17.18.3]**
`components/ProjectTimeline.tsx:61-64` and `components/ArchitectureMap.tsx:107,117`:
a failed fetch sets `error` and the render is gated on `!error` — the state is
never reset, so one network blip during an Observatory load bricks those panels
until a full page reload. **Fix:** reset `error` at the start of each fetch
(two-line fixes).

### Q10. World-sim beat vs god-tool read-modify-write race - **[FIXED v1.17.18.4]**
`services/world_sim/world_simulator.py`: `advance_day` (:207-250), `reset`
(:352-364), `set_time_scale` (:366-372), `trigger_disaster` (:374-416) each
open fresh sessions over the same engine; the `world-sim-tick` beat runs them
in scheduler threads while POST `/world-sim/tick|reset|accelerate|disaster`
run them in FastAPI's threadpool, with no lock. Two interleaved RMW cycles
both compute `day = N+1` → duplicate events/day numbers; a reset racing a
tick resurrects settlements mid-delete. SQLite serializes writes, not logic.
**Fix:** module-level `threading.Lock` around mutating methods.

---

## P2 — track / fix opportunistically

### Backend API & core
| # | Finding | Evidence |
|---|---------|----------|
| C1 | ~~Six copies of `_project_or_404`~~ **[FIXED v1.17.18.4]** - shared `api/v1/_deps.py` — should be one shared dependency | projects.py:18, builds.py:22, tests.py:20, testers.py:22, security.py:20, rag.py:32 |
| C2 | Negative `limit` bypasses clamp → negative LIMIT means "unlimited" in SQLite | system.py:62-66 (+ world_sim.py:44); contrast rag.py:201 and observatory's `Query(ge=1, le=1000)` |
| C3 | ~~`/rag/query` pins threadpool workers~~ **[FIXED v1.17.18.4]** (`ollama_timeout_seconds`) — a few concurrent queries starve all other sync endpoints | rag.py:58-85, config.py:46 |
| C4 | ~~role accepts any string~~ **[FIXED v1.17.18.4]**; garbage roles persist and echo back | schemas/chat.py:13, rag.py:206-231 |
| C5 | Raw-dict responses without models: all of system.py, portfolio summary, security clear_resolved | system.py:22-66, portfolio.py:48-54, security.py:52-58 |
| C6 | Sessions list N+1: per-session project + checkpoint + screenshot queries = 3N+1 per dashboard poll | sessions.py:41-79 |
| C7 | PATCH verb is the only non-GET/POST in the API (conventions say POST for state changes) | sessions.py:91 |
| C8 | Project files endpoint unbounded (47k-file trees serialize tens of MB) | projects.py:38-44, repositories/file.py:12 |
| C9 | ~~Chat history returns oldest 500~~ **[FIXED v1.17.18.4]** → returns **oldest** 500; newer messages unreachable past 500 rows | rag.py:197-202 |
| C10 | Stale doc drift post-Sprint-15: "CORS" (main.py docstring), "Celery beat" (world_sim.py:5), "docker compose --profile ollama" ×2 (cli.py:128-134,195-201) | see refs |
| C11 | ~~dead `host` setting~~ **[FIXED v1.17.18.4]** (removed from config + settings catalog; port resolved once in run.py per Q1); port defined independently in config.py:35 and run.py:173 — also resolved by Q1's single-resolution fix | config.py:32,35 |
| C12 | ~~CLI config set no-op~~ **[FIXED v1.17.18.4]** ("not implemented yet") | cli.py:308-321 |

### Services
| # | Finding | Evidence |
|---|---------|----------|
| S1 | ~~Systematic unclosed-httpx-client pattern~~ **[FIXED v1.17.18.3]**: `OllamaService.close()` now called at every construction site — system_service (lazy client + close in `report`), settings_service probe, triage summarize, rag (RagService.close via a yield dependency + CLI/tasks call sites), sync (`RepoSyncService.close` in run_sync/main.py probe); OllamaStatus no longer builds an unused pool for record_query-only callers | grep-verified |
| S2 | ~~Failed syncs leave no SyncRun row~~ **[FIXED v1.17.18.4]** (only HTTPError/FileNotFoundError caught) → dashboard last-sync pill shows stale success forever | sync_service.py:195-230,364-374 |
| S3 | ~~Indexer get-or-create race~~ **[FIXED v1.17.18.4]**: three concurrent entry points can double-insert; `Project.path` has no unique constraint | indexer.py:585-595, models.py:40 |
| S4 | ~~pyproject classifiers parsed as deps~~ **[FIXED v1.17.18.4]** (bare quoted-line regex; `::` not split) | indexer.py:549-555 |
| S5 | ~~`command_runner` duration + post-kill raise~~ **[FIXED v1.17.18.4]** on success; post-kill `communicate(timeout=5)` can raise out of contract leaving BuildLog rows half-written | command_runner.py:127,133-134,140 |
| S6 | ~~RAG retry-on-doomed-path~~ **[FIXED v1.17.18.4]**: fallback re-issues the same failing LLM request (another ≤1800 s wait); gate on real-vs-fake LLM | rag_service.py:750-755 |
| S7 | ~~Commit re-embedded every run~~ **[FIXED v1.17.18.4]** (files have embedding_id skip; commits don't) — repeated Ollama cost | rag_service.py:333-352 |
| S8 | Build `_free_ports` force-kills *any* process on declared ports, no ownership check (Rule 2 adjacent) | build_runner.py:269-279 |
| S9 | Hardcoded `github.com/jamesdileva/{name}` link assumes repo name == display name; wrong for juduncan/* checkouts | app_sessions.py:474 |
| S10 | Desktop runner injects real keyboard/mouse into whatever has focus — user-initiated and guarded, but deserves a docs warning (a tester run while the user types types into their session) | desktop_runner.py:109-132,205-220 |

### Data layer
| # | Finding | Evidence |
|---|---------|----------|
| D1 | ~~Dead tables~~ **[FIXED v1.17.18.4]**: `WorldSimState` (superseded by `WorldSimStateRow`), `ConfigEntry` — created every startup, never touched | models.py:243-251,254-259 |
| D2 | ~~Dead columns~~ **[FIXED v1.17.18.4]** `Project.health_score`, `GitCommit.added/modified/deleted_files`+`feature_tags`, `Dependency.latest_version/vulnerable/severity`, `KnowledgeSummary.confidence` | models.py:45,120-123,86-89,170 vs their Read schemas |
| D3 | ~~Dead repo methods~~ **[FIXED v1.17.18.4]**: `list_by_status`, `get_by_name`×2 | project.py:16-22, dependency.py:16-22 |
| D4 | ~~Dead schemas~~ **[FIXED v1.17.18.4]**: `ProjectDetail`, `ProjectHealth`, `FeatureTimelineItem` | schemas/project.py:43-55, git.py:23-29 |
| D5 | ~~Queries without LIMIT~~ **[FIXED v1.17.18.4]**: knowledge summaries, dependencies, files, security findings (build/test/git/session repos do cap correctly) | knowledge_summary.py:12-19, dependency.py:12-14, file.py:12-14, security.py:12-27 |
| D6 | ~~`Repository.count()` materializes the table~~ **[FIXED v1.17.18.4]** — now `SELECT COUNT(*)` | base.py:49-51 |
| D7 | ~~`SecurityRepository.delete_resolved` row-loops deletes and commits mid-method~~ **[FIXED v1.17.18.4]** — bulk DELETE, flush-only, caller commits (was the only repo that committed; no rollback anywhere in app/) | security.py:33-41 |
| D8 | ~~SyncRun accumulates unbounded~~ **[FIXED v1.17.18.4]** | models.py:262-277, sync_service.py:318-339 |
| D9 | ~~ChatMessageRead nullable mismatch~~ **[FIXED v1.17.18.4]** — persisted `None` would fail response validation | schemas/chat.py:21-25, models.py:222 |

### Parsers / testers / utils
| # | Finding | Evidence |
|---|---------|----------|
| T1 | `window_capture._descends_from` prefix match lacks separator boundary: `projects\foo` matches exes under `projects\foobar` → windows attributed to the wrong project | window_capture.py:246 |
| T2 | Headless Edge render uses no `--user-data-dir` → profile contention with running desktop Edge and inherited user cookies/storage (Rule 1 adjacent) | headless_render.py:49-58 |
| T3 | Four silent `except: pass` taskkill helpers across ag/hft/airadio/features — consolidate into `_helpers` with logging | ag.py:53, testers/hft_order_book.py:53, features/airadio.py:40, features/hft_order_book.py:100 |
| T4 | finsight fallback catches assertion errors too → shell-render defect masked as green; catch only `TesterEnvError` | finsight.py:28-35 |
| T5 | card_game feature treats *any* dialog as successful registration (failure alerts set the flag) | features/card_game.py:38-56 |
| T6 | tv_scheduler search-filter feature asserts nothing (fill → sleep → screenshot → green) — Rule 6 spirit violation | features/tv_scheduler.py:114-119 |
| T7 | Exception-taxonomy blur: TesterTimeoutError/EnvError raised for plain assertion failures (6 sites) — erodes Rule 7 failure provenance | cg.py(feature):51, card_game.py(feature):76, tv_scheduler.py(feature):95,109, demake.py(feature):36,57 |
| T8 | airadio.py contains baked-in mojibake (`â€”` ×4, byte-verified) — re-save as UTF-8 | features/airadio.py:1,8,33,76 |
| T9 | `language_detector` docstring promises vendor-dir exclusion; code walks node_modules/.venv/dist | language_detector.py:34-40 |
| T10 | Fixed sleeps where the codebase's own proven pattern is bounded retries: dinner_menu Vite probe (no retries vs card_game's 4), cg `ctx.wait(45)`, default_smoke `ctx.wait(20)` | dinner_menu_generator.py:23-27, cg.py:50, default_smoke.py:31 |
| T11 | Port declarations drift: demake declares ports=(8000,), cg/workflow_toolkit bind same port undeclared → inconsistent restart semantics | demake_engine.py, cg.py, workflow_toolkit.py |
| T12 | Tester slug registries duplicated by hand across testers/__init__, features/__init__ + import lists — 3 edit sites per new app | both __init__.py files |
| T13 | `run.py` leaks `PYTHONPATH=backend;…` into every launched child — root cause of workflow_toolkit's live `PYTHONPATH=""` patch; strip at runner level instead | run.py:165, workflow_toolkit.py:187 |
| T14 | Trivia: framework_detector case asymmetry (pyproject text not lowercased); dead tautological guards in command_extractor `_from_readme`; `_venv_python` iterdir unsorted; `pcPriClassBase=c_long` wrong on x64 (field unread); git_history pipe-in-author shifts fields | framework_detector.py:58-62, command_extractor.py:252-259,330-353,404-413, window_capture.py:55-62, git_history.py:30-33 |

### Frontend
| # | Finding | Evidence |
|---|---------|----------|
| F1 | ~~WebSocket liveness gap~~ **[FIXED v1.17.18.4]** — a dead-without-FIN socket (sleep/resume) stays "live" forever; server heartbeat could serve as watchdog | hooks/useWebSocket.ts:70-81, api/v1/ws.py:33-35 |
| F2 | ~~Dev proxy lacks ws:true~~ **[FIXED v1.17.18.4]** → dev never exercises the live WS path (prod unaffected) | vite.config.ts:9-14 |
| F3 | ~~BuildContext write-path is dead~~ **[FIXED v1.17.18.3]** — context deleted, tile now truthful (`trackJob`/`setJobStatus` never called) → Dashboard "Builds" tile permanently 0 while builds run. Wire Builds.tsx through it or delete it | contexts/BuildContext.tsx:22-35, Dashboard.tsx:48 |
| F4 | ~~~700 dead lines~~ **[FIXED v1.17.18.3]** — dead subtree removed: unrouted WorldSimulatorPage + WorldGridMap + api/world_sim.ts; api/tests.ts imported nowhere (dead or missing feature); dead types Dependency/DependencyType/ProjectStatus; unused listSummaries/getHealth | pages/WorldSimulatorPage.tsx, components/WorldGridMap.tsx, api/world_sim.ts, api/tests.ts, types/index.ts:30-54, api/rag.ts:98-107, api/client.ts:38-41 |
| F5 | Type drift: `ActivityEvent.id` non-null + `data` non-null vs live frames lacking id / null data; `ProjectFile` declares 3 phantom fields the API never returns | types/index.ts:19-28, api/system.ts:62-70, activity_bus.py:50-56 |
| F6 | Races: Projects file-list switch can render A's files under B (no sequencing); Builds duplicate-completion toast (interval re-enters finish during awaited refresh); RagChat late answer lands in switched room | pages/Projects.tsx:43-53, Builds.tsx:141-167, RagChat.tsx:104-115 |
| F7 | Security scan-all gives no progress and re-enables immediately when no project selected | Security.tsx:155-159 |
| F8 | Sessions.tsx is 937 lines / four components / 10 hooks in SessionDetail — split under components/sessions/* (Rule 4) | pages/Sessions.tsx |
| F9 | Copy-paste boilerplate: toast-error idiom ×15, page intro cards ×6 pages, poll-until-done effect ×3 — extract `toastError`, `<PageIntro>`, `<EmptyState>`, `usePollUntil` | Sessions/Security/Builds/KnowledgeExplorer/Layout etc. |
| F10 | a11y quick wins: modals lack Escape/focus trap/aria-modal; galaxy views' clickable SVG nodes unreachable by keyboard; header `<h1>` hardcoded "Dashboard" | Sessions.tsx:277-289+, ClusterView.tsx:193-251, MetroView.tsx:199-232, Layout.tsx:126-128 |

---

## P3 highlights (trivia — listed for completeness)

- `command_extractor` dead guards + `__main__.py` edge case (command_extractor.py:252-259,330-353)
- `chroma_manager.health()` recompute outside lock — benign duplicate work (chroma_manager.py:232-259)
- `release.py` collects files twice; dangling `- ` bullet if changelog empty (:48-88,:109)
- `build.py` npm/pytest invocations have no timeouts (interactive script, acceptable)
- activity-bus per-subscriber queues unbounded (bounded by dashboard usage)
- Dashboard prepend keys include index → full list re-render per event (cosmetic)

## Prior-audit cross-check

One claimed fix was structurally incomplete: A4's "kill in finally"
(`tester_runner.py:128-133`, this audit Q2). Worth re-verifying the remaining
v1.17.18.1 fixes with equal skepticism. All other docs/audit.md items were
excluded from scope here by design.

---

## Explicitly clean (verified, worth preserving)

- **No SQL injection surface**: all queries parameterized; the two raw-SQL
  spots use internal identifiers only.
- **Session lifecycle**: 100% context-managed across 30+ construction sites;
  zero leak paths. PRAGMA foreign_keys=ON + busy_timeout enforced and tested.
- **Blocking hygiene**: every route is sync `def` (threadpool-executed); no
  subprocess/sleep/http inside any `async def`; only async handlers are WS +
  exception handlers doing no blocking work.
- **Security posture (localhost app)**: SPA fallback traversal-safe; screenshot
  serving doubly guarded (filename whitelist + resolve containment); GitHub
  token redacted and never embedded in clone URLs; loopback guard enforced
  mechanically in feature nav; no CORS surface.
- **AI provenance (Rule 7)**: model + timestamp on every generated artifact
  (RAG answers, summaries, triage, query log).
- **Timeout discipline**: explicit timeouts on essentially every httpx call
  and subprocess in scope; wait loops have deadlines; no infinite-loop risk.
- **Frontend API layer**: single axios client, centralized error interceptor,
  relative URLs throughout (fully proxy-safe); zero `any`; strict types
  matching backend schemas (spot-checked 5 areas).
- **Determinism design** in world-sim rules engine (per-day seeded RNG) and
  command_extractor's ordered-confidence pipeline — genuinely well done.

---

## Recommended fix order (highest leverage first)

1. **Q2** tester_runner kill-ordering (orphan regression of shipped fix)
2. **Q1** run.py SENTINEL_PORT bind mismatch (operational footgun)
3. **Q3** wire the exception handler (fixes rag 500s class-wide)
4. **Q9** frontend error latches (two-line fixes)
5. **Q8** release bytecode exclusion (one line)
6. **S1** close httpx clients (one pattern clears six sites)
7. **Q6 + C2** push ORDER/LIMIT into SQL on hot endpoints
8. **Q4+Q5 together**: indexes + a schema-drift startup check
9. **F3/F4** decide BuildContext and the dead world-sim/tests subtree
10. Then batch the P2s by area (data-layer dead code first — cheap wins).

---

## Fixes applied — v1.17.18.3 (top batch, 2026-08-21)

| Item | Fix | Files | Tests |
|------|-----|-------|-------|
| Q2 | Kill the launcher tree FIRST in its own try/except, then end() in a second guard (neither masks the other); initial status is a legal terminal value (investigate) instead of unknown | services/tester_runner.py | existing tester-runner tests |
| Q1 | Resolve the port once (SENTINEL_PORT > --port), warn on override, thread it through both the occupancy probe and uvicorn bind; help text corrected | run.py | manual: --help + probe/bind read-through |
| Q3 | Single OllamaUnavailableError(SentinelError) in core/exceptions.py; central @app.exception_handler(SentinelError) maps via each subclass's status_code; sessions summarize no longer hand-maps; new regression test pins /rag/search -> 503 when Ollama down | core/exceptions.py, services/ollama_service.py, main.py, api/v1/sessions.py, tests/test_rag_api.py | test_rag_search_ollama_down_returns_503 + 48 API/triage/exception tests |
| Q9 | Reset the error latch at the start of every fetch attempt (and before loadMore) so a transient failure no longer permanently bricks the panels | components/ProjectTimeline.tsx, ArchitectureMap.tsx | vitest: 12 component tests |
| Q8 | _collect_files() excludes __pycache__/ dirs and .pyc/.pyo; dry-run verified zero bytecode in the release plan; also excludes .pytest/.mypy/.ruff caches | scripts/release.py | release.py --dry-run |
| S1 | Every per-request OllamaService client now closed: RagService.close() wired through a yield dependency (API), CLI ask/rag-index, rag tasks; OllamaStatus builds its client lazily and closes after report(); settings probe closes; RepoSyncService.close() called by run_sync (owned instances) and the startup configured-probe. Test fakes updated with close(). | system_service.py, rag_service.py, api/v1/rag.py, cli.py, tasks/rag_tasks.py, triage_service.py, settings_service.py, sync_service.py, main.py | full suite |
| Q6 | recent_queries pushes ORDER BY created_at DESC + LIMIT into SQL (was: materialize table, sort in Python on every /system/* poll). Retention prune for OllamaQueryLog still tracked under B3. | services/system_service.py | test_system_service 9 passed |
| C2 | Negative-limit holes closed with Query(ge=1, le=500)/(100, ge=1, le=500): /system/activity and /world-sim/history now reject out-of-range limits like observatory does | api/v1/system.py, api/v1/world_sim.py | existing suites |

**Verification:** backend 648 passed (full suite, coverage gate met); flake8 --max-line-length=100 clean; black/isort clean; frontend vitest 131 passed (18 files).

---

## Fixes applied — v1.17.18.3 (second batch, 2026-08-21)

| Item | Fix | Files | Tests |
|------|-----|-------|-------|
| Q4 | index=True on every FK column (projectfile/dependency/securityfinding/gitcommit/testresult/buildlog/knowledgesummary/chatmessage/appsession project_id; sessioncheckpoint/sessionscreenshot/triageanalysis session_id) plus created_at on activityevent and ollamaquerylog. New _migrate_indexes() backfills existing DBs idempotently via CREATE INDEX IF NOT EXISTS (names match SQLAlchemy's ix_<table>_<column> convention). | db/models.py, db/connection.py | test_fk_indexes_created_on_fresh_db, test_migrate_indexes_backfills_existing_db |
| Q5 | check_schema_drift(): compares live DB columns to model metadata after migrations; init_db logs loudly on drift and the new schema startup check surfaces it on /system (Rule 7 transparency) instead of failing to boot or silently 500-ing later. | db/connection.py, services/startup_check.py | test_check_schema_drift_detects_missing_column, test_startup_check_surfaces_schema_drift |
| F3 | Dead BuildContext deleted (trackJob/setJobStatus had zero callers); Dashboard's permanently-0 Builds tile replaced with a truthful Buildable count from the portfolio summary already loaded by the page. | contexts/BuildContext.tsx (deleted), app.tsx, pages/Dashboard.tsx, Dashboard.test.tsx | vitest Dashboard suite updated |
| F4 | ~790 lines of unreachable frontend removed: unrouted WorldSimulatorPage + WorldGridMap + api/world_sim.ts, never-imported api/tests.ts, dead types Dependency/DependencyType/ProjectStatus. ProjectFile type corrected to mirror ProjectFileRead exactly. Backend /tests and /world-sim endpoints untouched (still gated server-side). | pages/WorldSimulatorPage.tsx, components/WorldGridMap.tsx, api/world_sim.ts, api/tests.ts (all deleted), types/index.ts, Projects.test.tsx fixture | tsc --noEmit clean, vitest 131 pass |

---

## Fixes applied - v1.17.18.4 (third batch, 2026-08-21)

Scope note on Q10: the world-sim *dead code* removed in v1.17.18.3 was
frontend-only; the backend simulator is a live, settings-gated feature with
routed endpoints and tests, so the race was fixed rather than the feature
deleted.

| Item | Fix | Files | Tests |
|------|-----|-------|-------|
| Q10 | Process-wide `_WORLD_MUTATION_LOCK` around every mutating method (advance_day/catch_up, reset, set_time_scale, trigger_disaster); reads stay lock-free. Closes the beat-vs-god-tool duplicate-day / resurrect-settlement races. | services/world_sim/world_simulator.py | existing world-sim suite |
| S2 | run_sync catches unexpected exceptions and persists an error SyncRun - the dashboard last-sync pill can no longer show stale success after a crash | services/sync_service.py | existing sync tests |
| S3 | `_project_create_lock` serializes Project get-or-create across startup scan / scan-all beat / manual rescan; IntegrityError recovery re-fetches the winner; best-effort UNIQUE index on project.path (logs loudly if legacy dupes block creation) | services/indexer.py, db/connection.py | fixture updates (unique path) |
| S4 | `_deps_from_pyproject` now scopes to the PEP 621 `dependencies = [...]` array only - classifiers/keywords no longer become fake production dependencies | services/indexer.py | existing indexer dep tests |
| S5 | command duration is measured (time.monotonic), not the timeout ceiling; post-kill `communicate(timeout=5)` TimeoutExpired is contained so run_command always returns a structured CommandResult | services/command_runner.py | existing runner tests |
| S6 | removed the retry-on-doomed-path fallback in `_generate_with_metrics` (with a real LLM it re-issued the identical failing request); fakes short-circuit above as before | services/rag_service.py | rag service tests |
| S7 | `ingest_git_commits` skips commits already embedded via new `ChromaManager.existing_ids()` - no more re-embedding all commit messages on every index run | services/rag_service.py, chroma_manager.py | rag indexing tests |
| D1 | dead tables WorldSimState + ConfigEntry removed from models; init_db drops leftovers from old DBs (deterministic cleanup of grep-verified dead tables) | db/models.py, db/connection.py, tests/test_db.py | table-set assertions updated |
| D2 | dead always-null columns removed: GitCommit added/modified/deleted_files + feature_tags, Dependency latest_version/vulnerable/severity, KnowledgeSummary confidence (+ their Read-schema fields). Project.health_score was NOT dead weight - it is now populated by compute_portfolio_score so the Projects page badge finally shows real data. Old DBs keep inert columns (no DROP needed). | db/models.py, schemas/{git,knowledge,project}.py, services/portfolio_service.py | suites green |
| D3/D4 | dead repo methods (ProjectRepository.get_by_name/list_by_status, DependencyRepository.get_by_name) and dead schemas (ProjectDetail, ProjectHealth, FeatureTimelineItem) deleted with their exports | repositories/*, schemas/* | test_quality updated |
| D5/C8 | optional LIMITs on per-project queries (files, dependencies, security findings, knowledge summaries); GET /projects/{id}/files capped via Query(500, ge=1, le=1000); summaries endpoint capped at 200 | repositories/*, api/v1/projects.py, api/v1/rag.py | limit assertions |
| D6 | Repository.count() uses SELECT COUNT(*) instead of materializing the table | repositories/base.py | quality tests |
| D7 | delete_resolved is one bulk DELETE, flush-only; the route commits (transaction ownership back with the caller) | repositories/security.py, api/v1/security.py | delete_resolved test |
| D8 | SyncRun pruned to newest 50 rows on each persist | services/sync_service.py | sync tests |
| D9 | ChatMessageRead no longer inherits non-null sources; read shape tolerates legacy NULL rows. C4 also here: role is Literal["user","assistant"] | schemas/chat.py | chat API tests |
| C1 | shared project_or_404 dependency in api/v1/_deps.py replaces six byte-identical copies | api/v1/*.py | full API suite |
| C3 | /rag/query bounded by a 2-slot semaphore; excess requests get an honest 503 immediately instead of silently pinning threadpool workers for up to 1800 s | api/v1/rag.py | rag API tests |
| C9 | chat history selects the NEWEST page (DESC + LIMIT, re-reversed) - messages past 500 are reachable again | api/v1/rag.py | rag API tests |
| C10/C11/C12 | doc drift fixed (main.py CORS, world_sim.py Celery); dead SENTINEL_HOST setting removed from config + settings catalog; CLI config set exits 2 with guidance instead of exit-0 no-op | main.py, api/v1/world_sim.py, core/config.py, services/settings_service.py, cli.py | settings/config/cli suites |
| T1/T8/T9 | window_capture exe-prefix match requires a path-separator boundary (projects\foo no longer claims projects\foobar windows); airadio.py mojibake + BOM cleaned (byte-level fix); language_detector actually prunes node_modules/.venv/dist/etc as its docstring always promised | utils/window_capture.py, testers/features/airadio.py, utils/language_detector.py | parser/detector suites |
| F1/F2 | WebSocket liveness watchdog: if nothing (incl. the 30 s server heartbeat) arrives within 75 s while "open", force-close triggers reconnect - no more false "live" badge; dev proxy gains ws:true so development exercises the live WS path | hooks/useWebSocket.ts, vite.config.ts | vitest suite |

**Verification:** backend 652 passed (full suite incl. coverage gate); flake8/black/isort clean; frontend tsc clean + 131 tests pass; scripts/build.py --dist verified end-to-end and staged the rebuilt dashboard.

**New tracking note (flake):** two single-run failures during this batch were
a pre-existing order-dependent ChromaDB flake ("Nothing found on disk"
InternalError when multiple ChromaManager instances share a directory across
tests) - each full run failed a *different* test once, then a complete clean
652-pass run followed. Not introduced by these changes; worth its own look
(test isolation for the chroma singleton).
