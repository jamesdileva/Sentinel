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
- port: none (single-process game).
- fallback: `smoke:headless` script variant skips rendering; this tester
  always runs windowed because its value IS the visual evidence.
- cleanup: the app exits by itself; a best-effort `taskkill /T /IM` on the
  Godot engine image catches a hung hold window.
- sandbox notes: first run writes user://save/settings.cfg; achievements
  unlock locally during runs (harmless). Stage gates read the app log —
  `[smoke] <STAGE>=OK` lines printed by scripts/game/Game.gd.

Stages asserted (each gated on the app log, then screenshotted):
  MENU_SHOWN -> PLAYER_SPAWNED -> RESULT=OK (with GAMEPLAY_OK implied).
The full headless test suite (406 checks) runs first via ctx.cli.
"""

from app.testers import Tester
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
    kill_by_image_name,
)

GODOT_IMAGE_PREFIX = "Godot_v"


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


def _kill_hung_hold() -> None:
    """Best-effort cleanup if the hold window outlives the harness."""
    import subprocess

    subprocess.run(
        ["taskkill", "/T", "/F", "/IM", GODOT_IMAGE_PREFIX + "*"],
        capture_output=True,
        timeout=15,
    )


def run(ctx: TesterContext) -> None:
    commands = _commands(ctx)
    test_cmd = _require(commands, "test")
    startup = _require(commands, "startup")
    if "--smoke-hold" not in startup:
        startup += " --smoke-hold=15"

    # 1. Full deterministic suite (406 checks) before any GUI work.
    ctx.cli(test_cmd, timeout_s=900, expect_exit=0)

    # 2. Windowed self-driving smoke pass.
    ctx.mark_log()
    ctx.launch(startup)

    # 3. Stage-gated visual evidence. Each gate polls the app log, so slow
    # boots stretch the budget instead of racing a fixed sleep.
    ctx.wait_log("[smoke] MENU_SHOWN", timeout_s=90)
    ctx.screenshot("velocity main menu")

    ctx.wait_log("[smoke] PLAYER_SPAWNED", timeout_s=120)
    ctx.wait(4.0)  # let the map render + gameplay motion start
    ctx.screenshot("gameplay in map")

    # 4. Hard success assertion (default smoke only scans crash patterns).
    ctx.wait_log("[smoke] RESULT=OK", timeout_s=180)
    if ctx.log_contains("[smoke] RESULT=FAIL"):
        raise TesterAssertionError("smoke pass reported RESULT=FAIL")
    ctx.screenshot("smoke pass hold window")


TESTER = Tester(
    name="Velocity smoke",
    description=(
        "Run the full headless test suite (406 checks), then launch the "
        "windowed self-driving smoke pass: assert MENU_SHOWN, "
        "PLAYER_SPAWNED and RESULT=OK from the app log, capturing "
        "screenshots of the main menu, in-map gameplay and the hold "
        "window along the way."
    ),
    run=run,
    project_slug="Surfhop",
    kind="custom",
    auto_launch=False,
)
