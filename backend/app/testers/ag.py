"""AG tester — 2D-to-3D skeleton pipeline (CLI + tkinter GUI).

Verified ground truth (2026-08-15, updated 2026-08-19):
- venv `.venv_sf3d` (Python 3.11); `opencv-python-headless` was missing and
  installed — the CLI/GUI import `rigging_engine.image_processor` (cv2) at
  module level, so nothing ran without it.
- `static` subcommand works headlessly and deterministically:
  `-m rigging_engine.main static --front poses\\images\\front_tpose.png
  --side poses\\images\\side_tpose.png --output <file>.gltf` (exit 0, GLTF
  written).
- `animate --skeleton default --builtin idle` was BROKEN in the repo
  (main.py:283 `args.root_motion` NameError, exit 1) until AG fixed it in
  `bb27c7b` (main.py:415 `root_motion=getattr(args, "root_motion", False)`).
  The tester now asserts this path works and is green.
- The pytest suite is red in its own venv (12 env-gap failures: cv2/flask
  at collection/run) — the suite is exercised by the Tests page instead.
- The GUI is launched with the project's own `.venv_sf3d` python (launch
  rewriting) and keeps running after the session (leftover convention).
  Since v1.17.16 the click-through feature attaches to the window by title,
  so the tester reclaims its own previous GUI instances before launching a
  new one — otherwise the attach is ambiguous.
"""

import subprocess
import tempfile
from pathlib import Path

from app.testers import Tester
from app.testers._helpers import TesterContext, TesterEnvError

STATIC_CMD = (
    '"{}" -m rigging_engine.main static '
    '--front "poses\\images\\front_tpose.png" '
    '--side "poses\\images\\side_tpose.png" --output {}'
)
ANIMATE_CMD = (
    '"{}" -m rigging_engine.main animate --skeleton default --builtin idle --output {}'
)
GUI_CMD = "python -m rigging_engine.main gui"
GUI_WINDOW_TITLE = "AG Character & Weapon Studio"


def _reclaim_previous_gui() -> None:
    """Kill GUI instances this tester launched in earlier runs (they keep
    running per the leftover convention). Only the app's own window title
    is matched — never another python window."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/FI", f"WINDOWTITLE eq {GUI_WINDOW_TITLE}"],
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def run(ctx: TesterContext) -> None:
    root = Path(ctx.project.path)
    venv_python = root / ".venv_sf3d" / "Scripts" / "python.exe"
    if not venv_python.exists():
        raise TesterEnvError(f"AG venv python missing: {venv_python}")
    temp_dir = Path(tempfile.gettempdir()) / "sentinel-testers"
    temp_dir.mkdir(parents=True, exist_ok=True)

    _reclaim_previous_gui()

    static_out = temp_dir / "ag-static.gltf"
    ctx.cli(
        STATIC_CMD.format(venv_python, static_out),
        expect_stdout="Leg",
        expect_file=str(static_out),
        timeout_s=120,
    )
    ctx.checkpoint("static skeleton extraction verified")

    ctx.launch(GUI_CMD)
    ctx.wait(8)
    ctx.screenshot("tkinter GUI after launch")

    animate_out = temp_dir / "ag-anim.glb"
    ctx.cli(
        ANIMATE_CMD.format(venv_python, animate_out),
        timeout_s=180,
    )


TESTER = Tester(
    name="AG pipeline CLI + GUI",
    description=(
        "Extract a static skeleton from the bundled front/side T-poses "
        "(deterministic, headless) and verify the GLTF file; launch the "
        "tkinter GUI and screenshot it; then run the animate procedural "
        "path (green since AG fixed the root_motion NameError in bb27c7b). "
        "The pytest suite is NOT part "
        "of this tester: it is red in .venv_sf3d (env gaps) and is exercised "
        "by the Tests page instead."
    ),
    run=run,
    project_slug="Ag",
)
