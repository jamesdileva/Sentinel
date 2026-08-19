"""HFT-Order-Book tester — native SDL2 + Dear ImGui window presence.

Verified ground truth (2026-08-18, v1.17.15): HFT is a C++ SDL2 + OpenGL
+ Dear ImGui app; the packaged build/hft.exe (4.37 MB, built 2026-08-14)
is a self-contained simulator (GameManager synthesizes market data — no
external files, no network). It opens one SDL window whose process exe
lives under the project dir, so find_project_window matches it by
exe-path prefix without launcher detection (launcher_detect scans only
packaged Chromium/tauri layouts; native build/ exes are launched by the
tester itself).

Capture honest-limitation note: SDL2/OpenGL windows can render blank
through PrintWindow (GPU-composited); the window_capture layer falls
back to a screen crop automatically. The tester independently verifies
the capture has real content (>=8 gray levels), and the session
screenshot goes through the same window-targeted path.

Deliberate exclusions: no click-through yet — Dear ImGui exposes no
accessibility tree (Phase 3 chunk 2, gated). Deterministic presence +
render only (Rule 3).

Cleanup: the tester kills its own launched hft.exe tree at the end of
run() (taskkill /T /IM — the launch shell has no tracked pid; the exe
is a self-created entity of the session, so killing it is session
cleanup, not a user action).
"""

import subprocess
import time

from PIL import ImageGrab

from app.testers import Tester
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterTimeoutError,
)
from app.utils.window_capture import capture_window_content, find_project_window

HFT_CMD = r"build\hft.exe"
WINDOW_DEADLINE_S = 45
MIN_GRAY_LEVELS = 8


def _kill_launched_tree() -> None:
    try:
        subprocess.run(
            ["taskkill", "/T", "/F", "/IM", "hft.exe"],
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _wait_for_window(ctx: TesterContext) -> tuple[int, tuple[int, int, int, int]]:
    deadline = time.time() + WINDOW_DEADLINE_S
    while time.time() < deadline:
        window = find_project_window(ctx.project.path)
        if window is not None:
            ctx.checkpoint("hft.exe window visible")
            return window
        time.sleep(2)
    raise TesterTimeoutError("hft.exe never opened a window")


def _assert_content(hwnd: int, rect: tuple[int, int, int, int]) -> None:
    image = capture_window_content(hwnd, rect)
    if image is None:
        image = ImageGrab.grab(bbox=rect)
    histogram = image.convert("L").histogram()
    distinct = sum(1 for count in histogram if count)
    if distinct < MIN_GRAY_LEVELS:
        raise TesterAssertionError(
            f"HFT window capture looks blank ({distinct} gray levels)"
        )


def run(ctx: TesterContext) -> None:
    ctx.launch(HFT_CMD)
    try:
        hwnd, rect = _wait_for_window(ctx)
        _assert_content(hwnd, rect)
        ctx.checkpoint("window content rendered")
        ctx.screenshot("HFT window capture")
    finally:
        _kill_launched_tree()
    ctx.checkpoint("launched hft.exe cleaned up")


TESTER = Tester(
    name="HFT-Order-Book presence",
    description=(
        "Launch build/hft.exe (native SDL2 + Dear ImGui simulator), wait "
        "for its window (exe-path matched, no launcher detection), verify "
        "the captured content is real (>=8 gray levels; blank OpenGL "
        "PrintWindow renders fall back to a screen crop), and record the "
        "window capture as the session screenshot. No click-through — "
        "ImGui has no accessibility tree (Phase 3 chunk 2, gated)."
    ),
    run=run,
    project_slug="Hft-Order-Book",
    ports=(),
)
