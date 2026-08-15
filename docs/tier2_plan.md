# Tier 2 — Scripted Testers: Plan & Scope (docs/tier2_plan.md)

Target: v1.17.11.0. Turns the deferred "Tier 2 - Scripted testers" item in
docs/later.md into a shipped feature: per-app deterministic scripts that
build -> open -> drive an app -> record a session (markers, log slice,
screenshots) -> auto-set status. No AI anywhere (Rule 3); runs only when the
user clicks (Rule 2).

## Design decisions (locked 2026-08-15)

1. **Testers are Sentinel-side Python modules** (`backend/app/testers/*.py`),
   not in-repo JSON specs. Reason: full Python is strictly more capable than a
   step vocabulary — arbitrary waits, retries, window management, screenshots,
   and it can drive every app shape (HTTP, CLI, GUI, pytest suites). Provenance
   = Sentinel's own git history (Rule 7). Specs are reviewed like all Sentinel
   code and must never embed credentials; the runner never logs env values.
2. **Trigger**: a "Run tester" button on the Builds page (next to Build &
   Open), same project dropdown + JobEnvelope poll pattern as builds. Manual
   only.
3. **GUI screenshots**: Phase A testers launch the real app window, wait, and
   screenshot (feeds the Tier 4 portfolio). The auto-capture at session end
   always applies.
4. **Phase B breadth**: default smoke tester (launch -> wait -> log-error
   scan -> screenshot) auto-applies to launchable apps without a custom
   tester; custom HTTP testers for TV-Scheduler, WorkFlow-Toolkit,
   dinner-menu-generator, Card-Game. **Revoked at implementation (ground
   truth, 2026-08-15)**: MLBattles (no startup command at all), HFT-Order-Book
   (`build\hft.exe --orders 500` never exits — no stdout contract), ALGO
   backtester (no deterministic CLI contract), Python Projects (no runner) —
   these four report "No tester" in v1, documented honestly. 10 spec-only
   repos + khd4/trellis likewise report "No tester" and are skipped.
5. **No schema changes**: tester sessions flow through the existing AppSession
   model (title prefix `Tester: <name>`); status `passed` / `failed` /
   `investigate` (timeouts, port binds, environment gaps).

## Architecture

```
backend/app/testers/           one module per app + registry
  _helpers.py                  TesterContext (launch/http/cli/pytest/wait_log/wait/
                               checkpoint/screenshot) — wraps build_runner +
                               app_sessions; each step writes a
                               [sentinel] checkpoint: marker; asserts raise
                               TesterAssertionError
  cg.py, ag.py, demake_engine.py, default_smoke.py, tv_scheduler.py,
  workflow_toolkit.py, dinner_menu_generator.py, card_game.py
backend/app/services/tester_runner.py
                               resolve tester (custom slug -> default_smoke ->
                               none), create session, execute steps, end
                               session with status + auto screenshot
backend/app/tasks/tester_tasks.py   run_tester_task (JobEnvelope pattern)
backend/app/api/v1/testers.py      GET /testers/{project_id} (descriptor),
                                   POST /testers/run {project_id}
frontend/src/pages/Builds.tsx      "Run tester" button + job state + session link
```

TesterContext helpers (all bounded-timeout, all failures recorded as
checkpoints):

| Helper | Behavior |
|---|---|
| `launch(cmd, cwd, env)` | detached launch into `data/logs/apps/<slug>.log` |
| `http(method, url, expect=200, expect_body=...)` | httpx, short timeout |
| `cli(cmd, cwd, timeout_s, expect_exit=0, expect_stdout=..., expect_file=...)` | foreground, output appended to app log |
| `pytest(cmd, cwd, timeout_s)` | long-timeout CLI variant |
| `wait_log(pattern, timeout_s)` | poll the app log |
| `wait(seconds)` / `checkpoint(label)` / `screenshot(label)` | pause / marker / full-screen grab |

Determinism (Rule 3): matchers are substring/line/status-code only; env
pinning per step (`LLM_PROVIDER=mock` for CG, repo venv for AG); Demake
structural asserts only (its tilemap/audio use unseeded random). Secrets:
testers hold no credentials; runner redacts env values from logs.

## Phase A — hook projects

- **CG** (46 backend pytest, ~66s): launch FastAPI backend with
  `LLM_PROVIDER=mock` -> `/health` 200 -> `/` 200 -> POST `/api/topics/generate`
  -> GET `/api/topics` contains topic -> GET `/api/pipeline/job/{id}`
  (expected 200; **provably fails today** — renderer calls
  `/api/pipeline/jobs/{id}`, server route is `/api/pipeline/job/{id}`; a
  failing tester is a real catch) -> launch Electron -> wait -> screenshot ->
  pytest suite exit 0.
- **AG** (387 pytest green with `--ignore`; 12 env-gap failures otherwise):
  `animate --skeleton default --builtin idle` via `.venv_sf3d` python — **the
  repo is genuinely broken**: main.py:283 reads `args.root_motion` where
  `args` is out of scope (NameError, exit 1), so this step is red until AG
  fixes it (evidence in the session log); `static` CLI works and asserts the
  GLTF output file; launch GUI (`python -m rigging_engine.main gui`) -> wait
  -> screenshot. **Env note**: `opencv-python-headless` (cv2 5.0.0) had to be
  installed into `.venv_sf3d` — the CLI/GUI import cv2 at module level.
  No pytest step: AG's suite is red in its own venv (lives on the Tests page).
- **Demake Engine** (no tests): launch uvicorn -> `/health` 200 -> upload
  `backend/test_game_trailer.mp4` -> poll status until ready (max ~120s) ->
  manifest 200 -> asset 200 (structural asserts only; tilemap/audio use
  unseeded random).

## Phase B — simple testers

- default_smoke.py: launch via builds.md startup command -> wait for launch
  marker / N seconds -> scan log slice for `Traceback|FATAL ERROR|Cannot find
  module` -> screenshot -> passed/investigate. Applies to Airadio, FinSight
  (and any future launchable app without a custom tester).
- HTTP: TV-Scheduler (:3050 /health), WorkFlow-Toolkit (uvicorn
  app.main:app /health), dinner-menu (:5000), Card-Game (:3000 — PG is up;
  honest `failed` when PG is down).
- **No tester (ground-truth revocations)**: MLBattles (no startup command),
  HFT-Order-Book (`build\hft.exe --orders 500` never exits), ALGO backtester
  (no deterministic CLI), Python Projects (no runner). The Builds page shows
  a disabled "No tester" button and the descriptor endpoint returns 404 —
  better honest than flaky.

## Testing plan (Rule 6)

- Backend (`tests/test_testers.py`): runner lifecycle with a fake tester +
  in-process FastAPI test server on a random port (session auto-create/end,
  marker provenance, status mapping, screenshot on end); helpers unit tests
  (http/cli/wait_log/redaction/timeouts); registry resolution (custom vs
  default_smoke vs none); API tests (descriptor, run, 404s); JobEnvelope
  flow.
- Frontend: button visibility (descriptor present), run POST, session link,
  error toast.

## Docs & release

- docs/tier2_plan.md (this doc); docs/later.md Tier 2 -> DONE; changelogs in
  docs/01, 02, 03; AGENTS.md (no new env vars); version 1.17.11.0.
- `scripts/build.py --dist` gate (pytest + lint + frontend test + build);
  commit + push; restart; live-verify AG + CG + Demake testers end-to-end.
