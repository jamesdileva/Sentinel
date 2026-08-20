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

Ground truth (CORRECTED 2026-08-19 — the 2026-08-18 claim was wrong on
this machine): **Tcl/Tk 8.6.15 ships NO MSAA/UIA tree** (`tk::msaa` not
present) — pywinauto element-driving of tkinter widgets is impossible;
element names work ONLY on native Win32 dialogs (file open/save etc.).
Live-verified on 2026-08-19: tk ignores posted WM_* mouse messages
(SendMessage/PostMessage clicks change 0 pixels), so input must be
physical SendInput clicks with the window topmost at the cursor;
capture is via `PrintWindow(PW_RENDERFULLCONTENT|PW_CLIENTONLY)` through
ctypes (occlusion-independent; pywinauto's own capture_as_image returns
garbage and ImageGrab shows the screen). `SetWindowPos` HWND_TOPMOST
fails (ERROR_INVALID_WINDOW_HANDLE 1400) — moves work, but foreground
can only be obtained by SetForegroundWindow after BringWindowToTop and
fails while another app holds foreground rights → the engine raises an
honest, retryable TesterEnvError ("desktop busy"). **Dear ImGui exposes
no tree** — pywinauto can only send raw input; assertions degrade to
screenshots. The plan splits accordingly.

### Chunk 1 — UIA engine + AG features

- New engine `backend/app/services/desktop_runner.py`, `Feature.native=True`:
  pywinauto dependency (pure-python; new in `pyproject.toml`), attach by
  window title (UIA), click by SendInput, native dialogs driven by element
  name, same session/checkpoint/screenshot plumbing, same error mapping
  (`TesterAssertionError` / `TesterEnvError` / `TesterTimeoutError`) and
  per-feature budget. Deterministic guard mirrors the browser engine: window
  title must match a known app pattern (never drive an arbitrary window).
- AG features: the existing AG tester launches `rigging_engine/main.py gui`
  (tkinter) → the feature attaches by title `^AG Character & Weapon Studio$`
  → brings it to the foreground (honest env error when the desktop is busy,
  e.g. a game holds foreground) → asserts the layout signature via measured
  pixel anchors (tab accent, bottom-bar fill, status background — window
  moved to a fixed position first; clicks computed from the live rect) →
  loads a real source image (`poses/images/front_tpose.png`) via the native
  `Select T-Pose Image` dialog → clicks `Generate Character` → **asserts the
  progress state transition only** (status-region repaint; SF3D generation
  takes 5–10 min — completion is NOT asserted, same honest pattern as Cg's
  RESEARCHING; budget_s 600 for the transition window). Writes are the
  app's own output under the project (self-created entities).

  Live fixes landed in v1.17.16.0 (2026-08-19/20, on this machine):
  - Browse at **(642, 90)** (button spans x 598–687), Generate at
    **(360, 469)** (fill x 270–450, y 454–484) — measured from captures,
    not assumed.
  - The native dialog is driven by **keystrokes**: `Alt+N` (pywinauto
    `%n`) focuses the `File name:` box — it lives inside a DirectUIHWND the
    win32 backend cannot reach — then the path is typed and Enter submits.
    `dialog()` uses the **win32** desktop backend: the UIA desktop
    `wait('exists')` times out on native dialogs while win32 resolves
    instantly (`pywinauto.findwindows.find_windows()` hardcodes win32
    anyway).
  - The dialog opens **without foreground** (the parent keeps it), so the
    engine's new `Element.focus()` (`ShowWindow(SW_SHOWNORMAL)` +
    `SetForegroundWindow`) is applied before the keystrokes.
  - After the dialog closes, the tk modal loop unwinds a few ms later and
    `rest_path.set()` lands the path — the entry content check **polls for
    up to 15 s** instead of asserting once (race measured 2026-08-20).
  - The status log is Consolas 9pt: a new line is 1–2 px tall and can land
    between the step-4 sample rows (the 2026-08-19 failure saw the line
    render at y 543–549 while the grid only sampled 540/544/548) →
    `changed_pixels`/`wait_region_change` gained a `step` parameter and the
    transition check samples at **step 2, min 15 changed px**.
- Tests: fake-UIA-window unit tests (DesktopApp against a stubbed
  pywinauto.Desktop — title guard, foreground grant/busy, region diff,
  budget, keyboard type/press_alt/press_enter, wait_gone, content_pixels,
  thin-line step sampling) + fake-desktop feature runs + live E2E with
  gray-level verification. Live E2E green 2026-08-20 (all 13 steps:
  attach → foreground → layout signature → dialog → entry → transition).

### Chunk 2 — HFT input scripting (shipped v1.17.17.0)

Coordinate input against a fixed window geometry (pin position + verify
the client size first), asserting via screenshots (pixel-region checks).
No element tree: screenshot-only assertions (no text reads).

Ground truth (GUI.cpp, re-verified 2026-08-20): the window is
`gui.init("HFT Order Book", 1280, 760)` — **resizable**, SDL2 + OpenGL3 +
Dear ImGui 1.92.6; all random streams are seeded 42 (mt19937_64) so every
run renders deterministically. PrintWindow
(`PW_RENDERFULLCONTENT|PW_CLIENTONLY`) renders the GL window (no
screen-crop fallback needed). Menu buttons measured: `BENCHMARK MODE`
**(628, 323)** (blue #143B73), `TRADING GAME` **(628, 412)** (green
#1A5926), `MAIN MENU` **(1178, 723)** (present only on the benchmark
screen), `START TRADING` **(640, 409)** (240×48 centered at y=H·0.52,
GUI.cpp:208); the picker's stock cards draw in
a fixed grid (card 1 rect (12,106,404,300)) and the `TRADE THIS STOCK`
button is **flow-laid** (its Y shifts with the wrapped description — it is
the card child's last element, a full-card-width bar at the card bottom)
→ located by a fill-color search in the card-1 bottom band (unpressed
fill **#21262E** = ImGui FrameBg, tolerance 2), not a fixed coordinate.
**Live-verified gotcha (2026-08-20):** the button is NOT green — the menu
green #1A5926 and the picker's COL_GREEN "Start price" text #3DB04F are
different shades; the original green search matched the text. ImGui also
recolors a button to its hovered shade when the physical cursor is over
it (menu TRADING GAME #1A5926 → #263880 live-observed), so the engine
gained `move_mouse` and the feature parks the cursor at (10,10) before
color asserts. Benchmark = 2M
orders, ~1–2 s, and does **NOT** auto-return — the feature clicks MAIN
MENU to get back (clicking it mid-run leaves the sim loop in the
background; harmless, the next screen owns the window). Trading = 100k
orders at 1× ≈ 40 s and **auto-ends** on a pixel-stable SessionEnd; the
news banner shifts the panels 36 px (only the button row matters).

Shipped flow (`app/testers/features/hft_order_book.py`): launch
`build\hft.exe` (feature owns the process — the HFT presence tester stays
presence-only, Rule 4) → taskkill-reclaim a stale leftover → attach
`^HFT Order Book$` (Rule-1 guard) → bring to front → `pin_window(40, 40,
expected_client=(1280, 760))` (moves the window, then verifies the client
size the coordinates assume; SDL sizes are client-area so the size is
never forced — a resized window fails honestly) → main-menu signature via
`assert_pixel` on both buttons → BENCHMARK MODE (region change 500/20 →
settle 2/30 → screenshot) → MAIN MENU (signature re-assert) → TRADING
GAME (region change → screenshot) → `find_color_bbox` on the card-1
bottom band for the `TRADE THIS STOCK` bar (#21262E, tolerance 2,
min 1000 px, sampled step 2)
→ click its center → TradingReady (screenshot) → START TRADING (region
change → screenshot) → `wait_region_stable` (3 s stillness, 120 s cap) →
SessionEnd (screenshot). Cleanup is taskkill in a `finally` block.

New engine helpers (`app/services/desktop_runner.py`): `pin_window(x, y,
expected_client=None)` (SetWindowPos move with SWP_NOACTIVATE|NOZORDER|
NOSIZE; client-size verify → `TesterEnvError` on mismatch), `find_color_bbox`
(color search → bbox or None), `move_mouse(x, y)` (SetCursorPos without
clicking — parks the cursor off controls so ImGui's hover tint never
changes an asserted fill), `wait_region_stable(box, settle_s, timeout)`
(streak of consecutive identical captures — detects the static end-state of
the still-animating trading screen).

Tests: engine unit tests (pin move + flags, wrong-client env error, bbox
locate/tolerance/sparse-reject, stable-return/timeout) + fake-desktop
feature runs (happy path + honest failure when the card button is
missing) + registry gains Hft-Order-Book; 618 total, coverage 90.15%.
**Live E2E passed 2026-08-20 01:59–02:00** (all 19 steps: menu → benchmark
→ MAIN MENU → picker → card-1 click → TradingReady → START TRADING →
~40 s trading → SessionEnd; 6 stage screenshots).

### Chunk 3 — docs + tests + changelog

Phase 3 section (this), engine tests, changelog rows, later.md line update.

## Explicit exclusions

- **AG** (tkinter) — Playwright cannot drive it; pywinauto is Phase 3
  chunk 1 (engine shipped v1.17.16; tkinter has NO accessibility tree —
  measured SendInput clicks + native dialogs by element name).
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
- v1.17.16: Phase 3 — chunk 1 (pywinauto engine + AG features; ground truth
  corrected 2026-08-19: Tk has no accessibility tree), chunk 2 (HFT input
  scripting, gated), chunk 3 (docs/tests/changelog).
- v1.17.17.1: AG completion proof (wait_for_window on the app-spawned
  viewer, budget 900 s, live E2E 14 steps), Airadio screenshot feature
  (live title = ElmWave Network, not the BrowserWindow title), FinSight
  HTTP tester (cd electron && electron .; no auth; fallback), default_smoke
  runs the discovered test command first, docs/integration.md (tiers +
  checklist + Tauri skipped). Engine gains WindowNotFoundError +
  wait_for_window.
- Docs updated at implementation: `docs/02_Implementation_Guide.md` §14.8
  (tester section gains the feature layer), `docs/03_Sprint_Plan.md`.
