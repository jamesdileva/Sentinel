"""HFT native feature — drives the SDL2/OpenGL/ImGui simulator window
(docs/clickthrough_plan.md Phase 3 chunk 2, v1.17.17.0).

Ground truth (measured 2026-08-20, live): `build/hft.exe` opens a fixed
1280x760 SDL window titled "HFT Order Book". ImGui exposes no
accessibility tree, so the window is driven by physical SendInput clicks
at measured layout constants; every click is self-verified through its
effect (region repaint / screen transition). The window is pinned to a
fixed screen position first and its client size is verified (1280x760 —
SDL sizes are client-area; the measured coordinates assume that layout).

Live-verified capture fact (2026-08-20): PrintWindow
(PW_RENDERFULLCONTENT|PW_CLIENTONLY) DOES render this OpenGL window's
content (22 gray levels, button fills within tolerance) — no screen-crop
fallback needed (unlike the presence tester's belt-and-braces path).

Measured anchors (client px, 1280x760 layout):
- BENCHMARK MODE button (blue #143B73)    center (628, 323)
- TRADING GAME button (green #1A5926)     center (628, 412)
- MAIN MENU (benchmark screen, right bar) center (1178, 723)
- START TRADING (green #1A5926)           center (640, 409)
- stock card 1 rect                  (12, 106)-(404, 300)
- "TRADE THIS STOCK" button — flow-laid (Y shifts with the wrapped
  description), located by its fill-color search in the card-1 bottom
  band (unpressed fill #21262E = ImGui FrameBg)

Determinism (Rule 3): every random stream is seeded with 42
(mt19937_64 rng(42), OrderGenerator 42, RiskEventEngine 42) — the same
run every time. Benchmark = 2,000,000 orders (~1-2 s), does NOT
auto-return (MAIN MENU is clicked after completion — clicking it while
running leaves the sim loop going in the background). Trading = 100,000
orders at 1x speed (~40 s) then auto-ends on the static SessionEnd
screen. Only pixel-stable screens are asserted: MainMenu, StockPicker
(first visit), TradingReady, SessionEnd.

Flow (honest, Rule 3): reclaim stray hft.exe -> launch -> attach by
title -> bring to front -> pin position + verify client size -> menu
signature -> BENCHMARK MODE (region change, then settle = completion) ->
MAIN MENU (menu signature back) -> TRADING GAME (picker region change) ->
card 1 "TRADE THIS STOCK" via fill-color search -> TradingReady ->
START TRADING (trading screen region change) -> settle (~40 s trading ->
SessionEnd) -> screenshots through the run. Completion of the trading
phase is asserted ONLY as the screen going static — no text reads.
Cleanup: the feature kills its own launched hft.exe tree (self-created
entity).

The window is launched by the feature itself (the HFT presence tester
stays presence-only — Rule 4); a busy desktop that withholds foreground
is an honest TesterEnvError.
"""

import subprocess
from pathlib import Path

from app.services.desktop_runner import DesktopApp
from app.testers._helpers import (
    TesterAssertionError,
    TesterEnvError,
    kill_by_image_name,
)
from app.testers.features import Feature, FeatureContext

WINDOW_TITLE = r"^HFT Order Book$"
HFT_CMD = r"build\hft.exe"

# measured anchors (client px, fixed 1280x760 layout; see module docstring)
PIN_POS = (40, 40)
EXPECTED_CLIENT = (1280, 760)
MENU_BENCHMARK = (628, 323, (20, 59, 115))  # blue #143B73
MENU_TRADING = (628, 412, (26, 89, 38))  # green #1A5926
BENCHMARK_BUTTON = (628, 323)
TRADING_GAME_BUTTON = (628, 412)
MAIN_MENU_BUTTON = (1178, 723)
START_TRADING_BUTTON = (640, 409)  # 240x48 centered at y=H*0.52 (GUI.cpp:208)
# the picker's "TRADE THIS STOCK" button is the card child's last element:
# a full-card-width bar at the bottom of card 1 (measured bar rows
# y 272..297, fill #21262E — the ImGui FrameBg of the unpressed button;
# the menu's (26,89,38) green and the "Start price" COL_GREEN text are
# different shades and must NOT match)
CARD1_BUTTON_BOX = (12, 260, 404, 300)
BUTTON_BAR = (33, 38, 46)
FULL_BOX = (0, 0, 1280, 760)

TRANSITION_MIN_PX = 500
BENCHMARK_SETTLE_S = 2
BENCHMARK_WAIT_S = 30
TRADING_SETTLE_S = 3
TRADING_WAIT_S = 120

# card-button fill-search: the fill is exact and uniform (measured
# 2026-08-20: 9010 matching px across the card-1 bar, ~2250 sampled at
# step 2) — tolerance 2 and a generous floor reject text and borders
BUTTON_TOLERANCE = 2
BUTTON_MIN_PIXELS = 1000


def _kill_hft_tree() -> None:
    kill_by_image_name("hft.exe", tree=True)


def run(ctx: FeatureContext) -> None:
    exe = Path(ctx.project.path) / HFT_CMD
    if not exe.exists():
        raise TesterEnvError(f"HFT executable missing: {exe}")

    _kill_hft_tree()  # reclaim a leftover from a previous crashed run
    subprocess.Popen(
        [str(exe)],
        cwd=ctx.project.path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        app = DesktopApp(WINDOW_TITLE, budget_s=ctx.budget_s)
        app.connect()
        ctx.desktop = app
        ctx.step("attached to the HFT window by title")

        app.bring_to_front()
        ctx.step("window brought to the foreground")

        app.pin_window(*PIN_POS, expected_client=EXPECTED_CLIENT)
        ctx.step(f"window pinned at {PIN_POS}, client {EXPECTED_CLIENT} verified")

        app.move_mouse(10, 10)  # park the cursor off the buttons (hover tint)
        app.assert_pixel(*MENU_BENCHMARK)
        app.assert_pixel(*MENU_TRADING)
        menu_baseline = app.capture()
        ctx.step("main menu signature: BENCHMARK MODE + TRADING GAME present")
        ctx.shot("HFT main menu")

        app.click(*BENCHMARK_BUTTON)
        app.wait_region_change(menu_baseline, FULL_BOX, TRANSITION_MIN_PX, 20)
        ctx.step("BENCHMARK MODE clicked: benchmark screen appeared")
        app.wait_region_stable(FULL_BOX, BENCHMARK_SETTLE_S, BENCHMARK_WAIT_S)
        ctx.step("benchmark run completed (2M orders; screen settled)")
        ctx.shot("HFT benchmark complete")

        app.click(*MAIN_MENU_BUTTON)
        app.move_mouse(10, 10)
        app.assert_pixel(*MENU_BENCHMARK)
        app.assert_pixel(*MENU_TRADING)
        ctx.step("MAIN MENU: benchmark screen left, menu signature back")

        menu_baseline = app.capture()
        app.click(*TRADING_GAME_BUTTON)
        app.wait_region_change(menu_baseline, FULL_BOX, TRANSITION_MIN_PX, 20)
        ctx.step("TRADING GAME clicked: stock picker appeared")
        ctx.shot("HFT stock picker")

        app.move_mouse(10, 10)  # park off the card buttons (hover tint)
        bbox = app.find_color_bbox(
            CARD1_BUTTON_BOX, BUTTON_BAR, BUTTON_TOLERANCE, BUTTON_MIN_PIXELS
        )
        if bbox is None:
            raise TesterAssertionError(
                f"no 'TRADE THIS STOCK' button found in card 1 "
                f"({CARD1_BUTTON_BOX}) — bar fill {BUTTON_BAR} absent"
            )
        cx, cy = (bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2
        picker_baseline = app.capture()
        app.click(cx, cy)
        app.wait_region_change(picker_baseline, FULL_BOX, TRANSITION_MIN_PX, 10)
        ctx.step("card 1 selected: trading-ready screen appeared")
        ctx.shot("HFT trading ready")

        ready_baseline = app.capture()
        app.click(*START_TRADING_BUTTON)
        app.wait_region_change(ready_baseline, FULL_BOX, TRANSITION_MIN_PX, 10)
        ctx.step("START TRADING clicked: trading screen appeared")
        ctx.shot("HFT trading started")

        app.wait_region_stable(FULL_BOX, TRADING_SETTLE_S, TRADING_WAIT_S)
        ctx.step("trading session ended: screen settled (SessionEnd)")
        ctx.shot("HFT session end")
    finally:
        _kill_hft_tree()
    ctx.step("launched hft.exe cleaned up")


FEATURES = [
    Feature(
        name="HFT GUI click-through",
        description=(
            "Launch build/hft.exe (native SDL2 + OpenGL + Dear ImGui "
            "simulator — all random streams seeded 42, deterministic), "
            "attach by title, pin the window and verify the 1280x760 "
            "client size, then click through: BENCHMARK MODE (wait for the "
            "2M-order run to settle) -> MAIN MENU -> TRADING GAME -> card 1 "
            "'TRADE THIS STOCK' (located by its fill-color search in the "
            "card-1 bottom band — the button is flow-laid) -> START TRADING "
            "-> the ~40 s trading phase, "
            "asserted only as the screen settling on the static SessionEnd "
            "screen (no text reads, Rule 3). Screenshots at each stage. "
            "ImGui exposes no accessibility tree, so clicks are measured "
            "physical input; a busy desktop that withholds foreground is an "
            "honest env error. The feature owns launch + cleanup."
        ),
        run=run,
        native=True,
        budget_s=240,
    )
]
