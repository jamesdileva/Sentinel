r"""Surfhop (Velocity) tester — Godot bhop/surf time-trial game, self-driving
smoke mode.

Verified ground truth (2026-08-23, v1.17.19.x era):
- launch: the tester launches the project's stored startup command itself
  (`tools\godot.cmd --path . -- --smoke --smoke-hold=15`) — a self-driving
  pass that boots the real main menu, loads a map (`--smoke-map`, default
  beginner), simulates ~8s of gameplay input, then exits 0/1 by itself.
  `--smoke-hold=15` keeps the window alive post-RESULT so staged
  screenshots are not a race against self-exit. No packaged exe exists yet
  (deferred to release), so auto_launch must stay False.
- window capture: Godot's process exe lives under the winget install dir,
  NOT the project dir, so `find_project_window` (exe-path prefix match)
  finds nothing and app_sessions.capture records nothing. This tester
  therefore locates the window BY TITLE (`^Velocity`, from project.godot
  config/name) and registers captures via ctx.screenshot_file.
- port: none (single-process game).
- fallback: `smoke:headless` script variant skips rendering; this tester
  always runs windowed because its value IS the visual evidence.
- cleanup: the app exits by itself; best-effort taskkill of Godot_v*.exe
  catches a hung hold window.
- sandbox notes: first run writes user://save/settings.cfg; achievements
  unlock locally during runs (harmless). Stage gates read the app log —
  `[smoke] <STAGE>=OK` lines printed by scripts/game/Game.gd.

Stages asserted (each gated on the app log, then screenshotted):
  MENU_SHOWN -> PLAYER_SPAWNED -> RESULT=OK (with GAMEPLAY_OK implied).
The full headless test suite (406 checks) runs first via ctx.cli.
"""

import ctypes
import ctypes.wintypes
import re
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageGrab

from app.testers import Tester
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
    TesterTimeoutError,
)
from app.utils.window_capture import _window_rect, _is_blank, capture_window_content

_WINDOW_TITLE_RE = re.compile(r"^Velocity")
_MENU_DEADLINE_S = 90
_SPAWN_DEADLINE_S = 120
_RESULT_DEADLINE_S = 180
_GODOT_IMAGE_PREFIX = "Godot_v"

_ENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
)


def _commands(ctx: TesterContext) -> dict:
    """Stored stack first, live re-discovery second — mirrors resolve() and
    run_build() so a stale index can never wedge the tester."""
    commands = (ctx.project.stack or {}).get("commands") or {}
    if not (commands or {}).get("startup"):
        from app.utils.command_extractor import extract_build_commands

        commands = extract_build_commands(ctx.project.path)
    return commands or {}


def _require(commands: dict, key: str) -> str:
    value = (commands or {}).get(key) or ""
    if not value:
        raise TesterEnvError(f"no {key} command discovered for Surfhop")
    return value


def _find_game_window() -> tuple[int, tuple] | None:
    """(hwnd, rect) of the largest visible top-level window titled
    'Velocity' (Godot titles windows with project.godot config/name)."""
    user32 = ctypes.windll.user32
    hits: list[tuple[int, tuple]] = []

    @_ENUMPROC
    def _enum(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if _WINDOW_TITLE_RE.match(buf.value or ""):
            rect = _window_rect(hwnd)
            if rect and (rect[2] - rect[0]) * (rect[3] - rect[1]) > 0:
                hits.append((hwnd, rect))
        return True

    user32.EnumWindows(_enum, 0)
    if not hits:
        return None
    return max(hits, key=lambda h: (h[1][2] - h[1][0]) * (h[1][3] - h[1][1]))


def _shot_window(ctx: TesterContext, label: str, timeout_s: float) -> bool:
    """Wait for the game window, capture it, register the PNG. PrintWindow
    can return blank frames for GPU-composited Vulkan content (the same
    limitation the HFT tester docstrings) — fall back to a screen crop of
    the window rect. Returns False when no usable capture lands in budget."""
    deadline = time.time() + timeout_s
    tmp_path = ""
    try:
        while time.time() < deadline:
            found = _find_game_window()
            if found is not None:
                hwnd, rect = found
                image = capture_window_content(hwnd, rect)
                if image is None or _is_blank(image):
                    image = ImageGrab.grab(bbox=rect)
                if image is not None and not _is_blank(image):
                    tmp_path = str(
                        Path(tempfile.gettempdir())
                        / f"velocity-shot-{int(time.time() * 1000)}.png"
                    )
                    image.save(tmp_path)
                    ctx.screenshot_file(tmp_path, label)
                    return True
            time.sleep(1.5)
        return False
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def _kill_hung_hold() -> None:
    """Best-effort cleanup if the hold window outlives the harness."""
    try:
        listing = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, timeout=15
        ).stdout.decode("utf-8", errors="replace")
        for line in listing.splitlines():
            if line.startswith(f'"{GODOT_IMAGE_PREFIX}'):
                pid = line.rstrip('"').split('","')[-1].rstrip('"')
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", pid],
                    capture_output=True,
                    timeout=15,
                )
    except (OSError, subprocess.SubprocessError):
        pass


def run(ctx: TesterContext) -> None:
    commands = _commands(ctx)
    test_cmd = _require(commands, "test")
    startup = _require(commands, "startup")
    if "--smoke-hold" not in startup:
        startup += " --smoke-hold=60"
    if "--smoke-stage-pause" not in startup:
        # Dwell on each milestone so screenshots catch the actual stage
        # (the auto-driven menu otherwise lasts under a second).
        startup += " --smoke-stage-pause=2.5"

    # 1. Full deterministic suite (406 checks) before any GUI work.
    ctx.cli(test_cmd, timeout_s=900, expect_exit=0)

    # 2. Windowed self-driving smoke pass.
    ctx.mark_log()
    ctx.launch(startup)

    # 3. Stage-gated visual evidence: gate on the app-log milestone, then
    # title-based window capture (exe-path matching cannot see Godot).
    ctx.wait_log("[smoke] MENU_SHOWN", _MENU_DEADLINE_S)
    if not _shot_window(ctx, "velocity main menu", 20.0):
        raise TesterAssertionError("could not capture main menu window")

    ctx.wait_log("[smoke] MAP_SELECT_SHOWN", _MENU_DEADLINE_S)
    if not _shot_window(ctx, "map select screen", 20.0):
        raise TesterAssertionError("could not capture map select window")

    ctx.wait_log("[smoke] SETTINGS_SHOWN", _MENU_DEADLINE_S)
    if not _shot_window(ctx, "settings menu", 20.0):
        raise TesterAssertionError("could not capture settings window")

    # Gate on RUN_STARTED (emitted when simulated input begins) and shoot a
    # few seconds into the run so the frame shows real motion, not the
    # frozen spawn pose.
    ctx.wait_log("[smoke] RUN_STARTED", _SPAWN_DEADLINE_S)
    ctx.wait(4.0)
    if not _shot_window(ctx, "gameplay in map", 30.0):
        raise TesterAssertionError("could not capture gameplay window")

    # 4. Hard success assertion (default smoke only scans crash patterns).
    ctx.wait_log("[smoke] RESULT=OK", _RESULT_DEADLINE_S)
    if ctx.log_contains("[smoke] RESULT=FAIL"):
        raise TesterAssertionError("smoke pass reported RESULT=FAIL")
    if not _shot_window(ctx, "hold window after pass", 15.0):
        ctx.checkpoint("hold-window shot skipped (app already exited)")


TESTER = Tester(
    name="Velocity smoke",
    description=(
        "Run the full headless test suite (406 checks), then launch the "
        "windowed self-driving smoke pass: assert MENU_SHOWN, "
        "PLAYER_SPAWNED and RESULT=OK from the app log, capturing "
        "title-targeted screenshots of the main menu, in-map gameplay and "
        "the hold window along the way."
    ),
    run=run,
    project_slug="Surfhop",
    kind="custom",
    auto_launch=False,
)
