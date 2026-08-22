"""Airadio screenshot feature — packaged Electron app, window-targeted only.

The project ships an electron-builder package (`release\\win-unpacked`) whose
window title is `ElmWave Network` (the renderer HTML <title>; the packaged
BrowserWindow title is `WestWaveGem` but the page title wins). The app's UI
is sparse and Streamlabs-dependent (no reliable layout anchors), so the
feature asserts only what is deterministic: launching the packaged exe
opens its window (attach by title, Rule 1 — only the declared window is
ever driven), the window paints non-blank content, and the process is
cleaned up after the session. No clicks, no foreground moves, no mouse
needed (v1.17.17.1).

A blank capture (Chromium sometimes paints nothing via PrintWindow) trips
the shot's blank gate and fails the feature honestly; the documented
fallback is the proven CDP/electron engine from v1.17.14.4.
"""

import subprocess
import time
from pathlib import Path

from app.services.desktop_runner import DesktopApp
from app.testers._helpers import TesterEnvError, kill_by_image_name
from app.testers.features import Feature, FeatureContext

WINDOW_TITLE = r"^ElmWave Network$"  # verified live 2026-08-20 (page <title>)
EXE = r"release\win-unpacked\WestWaveGem Radio.exe"
SETTLE_S = 8  # allow the renderer to paint before the screenshot


def _kill() -> None:
    """Kill any WestWaveGem instance this feature launched. The image name
    is the app's own packaged exe — never a generic process."""
    kill_by_image_name("WestWaveGem Radio.exe")


def run(ctx: FeatureContext) -> None:
    exe = Path(ctx.project.path) / EXE
    if not exe.exists():
        raise TesterEnvError(f"packaged Airadio exe missing: {exe}")
    _kill()
    subprocess.Popen(
        [str(exe)],
        cwd=str(ctx.project.path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        app = DesktopApp(WINDOW_TITLE, budget_s=ctx.budget_s)
        app.connect()
        ctx.desktop = app
        ctx.step("attached to the ElmWave Network window by title")
        time.sleep(SETTLE_S)
        ctx.shot("ElmWave Network app window")
    finally:
        _kill()
    ctx.step("WestWaveGem Radio launched, captured and cleaned up")


FEATURES = [
    Feature(
        name="ElmWave Network window screenshot",
        description=(
            "Launch the packaged electron exe, attach to its WestWaveGem "
            "window by title and screenshot it. The app's UI is sparse and "
            "Streamlabs-dependent, so no layout anchors are asserted: a "
            "non-blank window capture is the honest completion signal "
            "(blank Chromium PrintWindow output fails the shot's blank "
            "gate). No mouse or foreground moves — window-targeted only "
            "(v1.17.17.1)."
        ),
        run=run,
        native=True,
    ),
]
