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

## Round 3 (v1.17.15) — remaining app coverage: Algo Trader + HFT

Two indexed projects still have no tester (their startup commands are empty,
so even default smoke cannot launch them). Both get custom testers + (for
Algo Trader) a browser feature. No new engine.

### Algo Trader

Two surfaces, both fit existing infrastructure:

| Surface | Type | Coverage |
|---|---|---|
| `web/app.py` | Flask dashboard on **:5000** (reads `data/algo_trader.db`, read-only views: positions reconstructed from orders, recent orders) | Tester `ctx.launch` → `ctx.http` on `/`, `/api/positions`, `/api/orders/recent` (200 + body markers) → one browser **feature**: dashboard renders, tables populate — read-only, no Alpaca writes |
| `build/backtester.exe`, `build/trader.exe` | CLI (no UI — console output only) | Real backtest `ctx.cli` (`backtester.exe 2026-07-01 2026-07-24` — bars confirmed in backtest.db, fully local; asserted on the `=== BACKTEST COMPLETE ===` marker + exit 0); output lands in the app log, so the "console screenshot" is the log itself. `trader.exe` excluded (live loop, not deterministic). |

Notes:
- Flask needs an interpreter with Flask installed — no venv in the repo;
  the launch command's `python` passes through to the system Python
  (Flask 3.1.3 on this machine).
- The real backtest wipes + repopulates only `data/backtest.db` (the
  app's own backtest copy; `data/algo_trader.db` — the dashboard's DB —
  is untouched).

### HFT Order Book — presence tester

- `build/hft.exe` (4.37 MB, native C++ SDL2 + OpenGL + Dear ImGui) — **not**
  Chromium, no DOM, no accessibility tree. Playwright/CDP cannot drive it;
  pywinauto element-driving cannot see it (ImGui draws its own controls).
- Coverage: tester `ctx.launch` the exe → window capture via
  `find_project_window` (matches by **exe path under the project** — works
  for `build/hft.exe` out of the box) + gray-level check → in-tester
  session-end tree kill (taskkill /T /IM hft.exe — the launch shell has no
  tracked pid, so the tester cleans up its own exe). Honest caveat:
  SDL2/OpenGL windows can render blank through `PrintWindow` (GPU
  compositing) — the existing screen-crop fallback covers that; live E2E
  confirmed real captures.
- `launcher_detect.py` is **not** extended for native `build/` exes — the
  launch stays in the tester (minimal change; re-visit if more native apps
  appear).
- Real click-through is Phase 3 chunk 2 (input scripting, gated).

## Phase 3 (v1.17.16) — native desktop UIA (chunked)

Ground truth (verified 2026-08-18): **tkinter exposes a real MSAA/UIA
accessibility tree** — pywinauto element-driving works (buttons, entries by
name). **Dear ImGui exposes no tree** — pywinauto can only send raw input
(clicks at coordinates, keys); assertions degrade to screenshots. The plan
splits accordingly.

### Chunk 1 — UIA engine + AG features

- New engine `backend/app/services/desktop_runner.py`, `Feature.native=True`:
  pywinauto dependency (pure-python; new in `requirements.txt`), attach by
  window title, click/type by element name, same session/checkpoint/
  screenshot plumbing, same error mapping (`TesterAssertionError` /
  `TesterEnvError` / `TesterTimeoutError`) and per-feature budget.
  Deterministic guard mirrors the browser engine: window title must match a
  known app pattern (never drive an arbitrary window).
- AG features: launch `rigging_engine/main.py gui` (tkinter; existing AG
  tester already launches it) → assert the main window + key widgets
  (Notebook tabs, "View Last Export" bar button) → load a real source image
  (`poses/images/` PNG, e.g. a run-cycle pose) via the file dialog →
  start generation → **assert the progress state transition only**
  (SF3D generation takes 5–10 min — completion is NOT asserted, same honest
  pattern as Cg's RESEARCHING; budget_s ~600 for the transition window).
  Writes are the app's own output under the project (self-created entities).
- Tests: fake-UIA-window unit tests + live E2E with gray-level verification.

### Chunk 2 — HFT input scripting (stretch, gated)

Coordinate/keyboard input against a fixed window geometry (set position +
size first), asserting via screenshots (pixel-region checks). Fragile by
nature — only attempted if Chunk 1 ships AND the Round 3 HFT presence
captures show a stable render. Honest fallback: presence-only forever.

Button ground truth (GUI.cpp, verified 2026-08-19): main menu has
`BENCHMARK MODE` (GUI.cpp:134 — auto-runs benchmark mode) and
`TRADING GAME` (GUI.cpp:153 → `GamePhase::StockPicker`); the picker
draws 2 rows of 3 clickable stock cards (drawStockPicker, GUI.cpp:536,
fixed cardW/cardH) then `START TRADING` (GUI.cpp:208) begins the
1–2 min trading phase; `MAIN MENU` (GUI.cpp:472) returns. The window is
fixed-size (GUI::init takes width/height) and ImGui lays out
deterministically, so button coordinates are stable once the window
position is pinned via SetWindowPos. Target flow: click BENCHMARK MODE
→ screenshot; MAIN MENU → TRADING GAME → click one card → START TRADING
→ 3–4 screenshots across the run. No element tree: screenshot-only
assertions (no text reads).

### Chunk 3 — docs + tests + changelog

Phase 3 section (this), engine tests, changelog rows, later.md line update.

## Explicit exclusions

- **AG** (tkinter) — Playwright cannot drive it; pywinauto/UIA is Phase 3
  chunk 1 (element-driven; tkinter has a real accessibility tree).
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
- v1.17.15: Round 3 app coverage — Algo Trader (Flask dashboard tester +
  browser feature + CLI steps for backtester/trader) and HFT Order Book
  (presence tester on build/hft.exe).
- v1.17.16: Phase 3 — chunk 1 (pywinauto UIA engine + AG features), chunk 2
  (HFT input scripting, gated), chunk 3 (docs/tests/changelog).
- Docs updated at implementation: `docs/02_Implementation_Guide.md` §14.8
  (tester section gains the feature layer), `docs/03_Sprint_Plan.md`.
