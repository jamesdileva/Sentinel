# Click-Through Features (UI Automation) — Plan & Scope (docs/clickthrough_plan.md)

Turns the deferred "UI automation (pywinauto/Playwright)" refinement in
later.md (Tier 2) into a shipped feature: scripted Playwright click-through
drives the real UI of Sentinel's indexed apps — click, fill, assert the DOM
result, screenshot each step — after the deterministic smoke testers pass.
No AI anywhere (Rule 3); runs only via the user-initiated tester flow
(Rule 2); localhost-only (Rule 1); every feature ships with tests (Rule 6).

## Rules fit (locked)

| Rule | Enforcement |
|------|-------------|
| 1 (local) | Hard loopback guard: every navigation must resolve to 127.0.0.1 / localhost / ::1; the engine refuses any other host before goto. |
| 2 (no autonomous) | Features run only inside the existing "Run tester" button flow. No scheduled feature runs. |
| 3 (determinism) | Scripted assertions only (Playwright auto-waiting + expect). No AI, no LLM coupling: dinner-menu's "Suggest Meal" (Ollama) is intentionally NOT a feature. |
| 6 (testable) | Engine unit tests with a stubbed browser factory; registry test; live E2E per app with screenshot gray-level verification. |

## Architecture

```
backend/app/testers/features/         one module per app (mirrors testers/)
  __init__.py                         Feature dataclass + FEATURES registry
  _context.py                         FeatureContext (page fixture + step/shot)
  dinner_menu.py, tv_scheduler.py, card_game.py, cg.py, demake.py
backend/app/services/feature_runner.py    engine: browser lifecycle, guard,
                                          error mapping, bounded execution
backend/app/services/tester_runner.py     +1 hook after tester.run(ctx)
backend/app/api/v1/testers.py            descriptor gains features list
```

- **`Feature`** (frozen dataclass): `name`, `description`, `run(ctx)` — mirrors
  `Tester`. Registry `FEATURES: dict[slug, list[Feature]]`, built like TESTERS.
- **`FeatureContext`** wraps the existing `TesterContext` (same session /
  checkpoint plumbing):
  - `ctx.page` — Playwright `Page` (browser tab or the packaged app's
    window for electron features, v1.17.14.4)
  - `ctx.go(url)` — loopback-validated navigation (the only sanctioned way to
    move the page)
  - `ctx.step(label)` — checkpoint
  - `ctx.shot(label)` — `page.screenshot()` → temp PNG → existing
    `register_screenshot()` (v1.17.13.1 path), so shots land on the Sessions
    page exactly like headless renders; blank frames (<8 gray levels) raise
    TesterAssertionError like render_and_register does
- **Browser**: Playwright Python **sync API, `channel="msedge"`** — drives the
  installed system Edge (no browser download; consistent with headless_render).
  `headless=True` by default; `SENTINEL_FEATURES_HEADED=1` for debugging.
  Playwright is added to `backend/requirements.txt`.
- **Hook**: `TesterRunner.run()` — smoke (`tester.run(ctx)`) → features
  (`FeatureRunner.run(...)`) → `_auto_render` (dedupes because features
  already registered screenshots — existing behavior, no change).
- **Status mapping** (reuse the tester semantics):

| Failure | Status |
|---|---|
| `TesterAssertionError` (incl. Playwright `TimeoutError`/`Error` translated) | `failed` |
| `TesterTimeoutError` / `TesterEnvError` (browser launch, missing Edge, guard refusal) | `investigate` |

- **Bounded execution**: Playwright's per-action default timeout (15 s) +
  a per-feature deadline checked by `step`/`shot`/`go`; a feature past its
  budget raises TesterTimeoutError. No unbounded loops possible.
- **No schema changes**: features ride the existing AppSession model.
  `GET /testers/{project_id}` gains `features: [{name, description}]`.

## Phase 1 (v1.17.14.0) — browser features

All five apps are DOM-based (verified by UI scan, 2026-08-17) and clickable:

| App | Features | Deterministic assertion |
|---|---|---|
| Dinner-Menu-Generator | add meal via modal; dark-mode toggle | meal text visible in list; toggle button label flips |
| TV-Scheduler | add show to watchlist; search filters it | row text visible; filtered list contains it |
| Card-Game | register throwaway account (`tester-<ts>`), login, spin $100 | logged-in UI; balance display changes after spin (never touches `james`/real accounts) |
| Cg | generate topics on Dashboard | topic rows appear |
| Demake-Engine | upload fixture .mp4 → GENERATE → CHECK IF READY → PLAY link | play link href visible (Phaser canvas page is the boundary) |

Locators are pinned against each app's actual markup during implementation
and refined in live E2E. External-API dependency risk (TV-Scheduler show
lookup, demake pipeline runtime ~30 s) is accepted: assertions are about the
UI's own response to the action, not external data correctness.

## Phase 2 (v1.17.14.4) — Electron desktop features (CDP engine)

Drives the packaged launcher (reuse `find_packaged_launcher`) for
WorkFlow-Toolkit (Templates → run Payroll Audit → report row) and
TV-Scheduler (add show via the real window). **Engine amendment
(v1.17.14.4): Playwright 1.62's python package ships no `p.electron`
wrapper** (the node driver has electron support, the wrapper does not —
verified `hasattr(p, 'electron')` → False), so the engine launches the
packaged exe with `--remote-debugging-port=<free>` +
`--user-data-dir=<temp sandbox>` and attaches via `connect_over_cdp` —
same Page API for features, zero new dependencies.

- **Data sandbox**: always launch with `--user-data-dir=<temp>` — the
  user's real app state is never touched. Verified, not assumed: the
  temp dir must gain Chromium profile files and the app's own state
  artifact (`tv_scheduler.db`, `data/` dir or `backend.log`) or the run
  is a TesterEnvError (Rule 1). Window URL must be file:// or loopback.
- **Port strategy**: TV-Scheduler's packaged backend hard-codes :3050 —
  the runner reclaims the tester-phase auto-launched instance
  (taskkill) before launching the sandboxed one; WFT uses pickFreePort
  (no conflict). The spawned tree is taskkilled on exit (self-created).
- **Feature model**: `Feature.electron=True` picks the electron engine;
  `budget_s` overrides the 120 s deadline (WFT feature: 180 s).
  `ctx.go()` is refused for electron features — the window is already on
  the app. TV-Scheduler's interim dev-stack fallback is removed: real
  TVMaze names never hit the stale asar's broken manual-add path.

## Explicit exclusions

- **AG** (tkinter) — Playwright cannot drive it; pywinauto/UIA is a separate
  future decision.
- **Demake `game.html`** (Phaser/WebGL canvas) and any canvas-only UI — the
  DOM boundary is the feature boundary.
- **Cg Publish page** (YouTube auth/upload) — irreversible actions (Rule 2).
- **Destructive actions** (TV-Scheduler Delete Show, dinner-menu Delete) —
  only ever exercised against entities the feature itself just created.

## Tests (Rule 6)

- Engine unit tests (`backend/tests/test_feature_runner.py`, browser factory
  stubbed): registry resolution + ordering; loopback guard (non-local URL
  refused); error mapping (Playwright timeout → TesterAssertionError, launch
  failure → TesterEnvError); shot registers a screenshot row + file;
  resolve no-op for projects without features; feature deadline enforcement.
- Registry test: `FEATURES` slug set matches expected.
- Live E2E: run each app's tester via `POST /api/v1/testers/run`, verify
  feature checkpoints + screenshot dimensions/gray levels; refine locators.
- Gate unchanged: `scripts/build.py --dist` (black/isort/flake8, 90%
  coverage floor, frontend tests).

## Rollout

- v1.17.14.0: engine + phase 1 (all 5 apps), changelog rows, later.md
  "UI automation remains future" line updated.
- v1.17.14.1–3: live-fix rounds (locator ground truth, real-name adds,
  scroll exploration, Session responsive polish).
- v1.17.14.4: phase 2 Electron features (CDP engine, sandbox, WFT Payroll
  Audit, TV real window) + this plan's Phase 2 header updated.
- Docs updated at implementation: `docs/02_Implementation_Guide.md` §14.8
  (tester section gains the feature layer), `docs/03_Sprint_Plan.md`.
