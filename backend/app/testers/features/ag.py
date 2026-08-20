"""AG native feature — drives the tkinter GUI (docs/clickthrough_plan.md
Phase 3 chunk 1, v1.17.16.0).

Ground truth (measured 2026-08-19, live): `rigging_engine/main.py gui`
opens a fixed 720x680 tk window titled "AG Character & Weapon Studio".
Tk on this machine exposes NO accessibility tree (Tcl/Tk 8.6.15 ships
no MSAA/UIA providers), so the tkinter widgets cannot be driven by
element name; the plan's chunk-2 technique is applied instead: physical
SendInput clicks at measured layout constants, with every click
self-verified through its effect. The app's native file dialog ("Select
T-Pose Image") is driven by keystrokes — its File name box lives inside
a DirectUIHWND that the win32 backend cannot reach (measured 2026-08-19);
Alt+N focuses it, the path is typed, Enter submits.

Measured layout anchors (client px, from a PrintWindow capture of the
running GUI):
- selected Notebook tab accent bar            (10, 20)  = (91,141,239)
- bottom bar "View Last Export" button fill (25, 510) = (35,38,46)
- status Text widget background           (100, 560)  = (21,23,28)
- Source "Browse..." button center            (642, 90)   (spans x 598-687)
- "Generate Character" button center          (360, 469)  (fill x 270-450, y 454-484)
- status widget box                        (8, 540)-(712, 668)
- Source entry box                         (45, 80)-(595, 105)
- Source entry text band                  (45, 86)-(595, 99)

The dialog is driven by keystrokes: Alt+N focuses its "File name:" box
(the box lives inside a DirectUIHWND the win32 backend cannot reach —
measured 2026-08-19), the path is typed, Enter submits. The pose path
then appears in the entry (measured ~1600 non-white px vs 0 empty).

Flow (honest, Rule 3): attach by title -> bring to front (busy desktop
is an env error, not a lie) -> theme-signature anchors -> click Browse
-> the native dialog must appear (verifies the click) -> Alt+N + type
the pose path + Enter (dialog must close, entry must show the path) ->
click Generate Character -> assert the progress transition ONLY: the
status region repaints (SF3D runs 5-10 min; completion is NOT asserted —
same pattern as Cg's RESEARCHING). The feature then waits for the
viewer window the app itself spawns at the end of a successful export
(gui.py:505-508 `_launch_preview`), attaches to it and screenshots the
generated character's 3D scene — completion proof without any text
read. budget_s ~900 covers the transition + the viewer wait.

The window is the one launched by the tester phase of this same session
(tester-run hook); a missing/busy window is an honest TesterEnvError.
"""

import time
from pathlib import Path

from app.services.desktop_runner import DesktopApp, wait_for_window
from app.testers._helpers import TesterAssertionError, TesterEnvError
from app.testers.features import Feature, FeatureContext

WINDOW_TITLE = r"^AG Character & Weapon Studio$"
VIEWER_TITLE = r"^AG (Animation )?Viewer"  # viewer.py:901 default + playback caption
POSE_IMAGE = r"poses\images\front_tpose.png"
DIALOG_TITLE = r"^Select T-Pose Image$"

# measured anchors (client px, fixed 720x680 layout; see module docstring)
TAB_ACCENT = (10, 20, (91, 141, 239))
BAR_BUTTON_FILL = (25, 510, (35, 38, 46))
STATUS_BG = (100, 560, (21, 23, 28))
BROWSE_BUTTON = (642, 90)  # live-measured 2026-08-19: button spans x 598-687
GENERATE_BUTTON = (360, 469)  # live-measured 2026-08-19: fill x 270-450, y 454-484
STATUS_BOX = (8, 540, 712, 668)
ENTRY_BOX = (45, 80, 595, 105)
ENTRY_TEXT_BAND = (45, 86, 595, 99)  # glyph band (excludes the sunken border)
ENTRY_EMPTY = (255, 255, 255)
ENTRY_MIN_TEXT_PX = 800  # measured ~1600 for the pose path

TRANSITION_WAIT_S = 120  # transition window after the generate click
VIEWER_WAIT_S = 600  # viewer wait after the transition (generation completes)
VIEWER_SETTLE_S = 4  # scene load before the screenshot


def run(ctx: FeatureContext) -> None:
    app = DesktopApp(WINDOW_TITLE, budget_s=ctx.budget_s)
    app.connect()
    ctx.desktop = app
    ctx.step("attached to the AG GUI window by title")

    app.bring_to_front()
    ctx.step("window brought to the foreground")

    app.assert_pixel(*TAB_ACCENT)
    app.assert_pixel(*BAR_BUTTON_FILL)
    app.assert_pixel(*STATUS_BG)
    ctx.step("layout signature: tabs, bottom bar and status widget present")

    pose = Path(ctx.project.path) / POSE_IMAGE
    if not pose.exists():
        raise TesterEnvError(f"pose image missing: {pose}")

    app.click(*BROWSE_BUTTON)
    dlg = app.dialog(DIALOG_TITLE)
    ctx.step("source Browse... opened the native file dialog")

    dlg.focus()  # the dialog opens without foreground — keys would hit the parent
    app.press_alt("n")  # focus the File name: box (DirectUIHWND — keyboard)
    app.type_text(str(pose))
    app.press_enter()
    dlg.wait_gone(10)
    # The dialog's native window disappears before the tk modal loop unwinds
    # and _browse_rest sets the path — poll, don't check once (race measured
    # 2026-08-20: entry still empty ~100ms after the dialog was gone).
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if app.content_pixels(ENTRY_TEXT_BAND, ENTRY_EMPTY) >= ENTRY_MIN_TEXT_PX:
            break
        time.sleep(0.5)
    else:
        raise TesterAssertionError(
            f"pose path did not land in the entry after the dialog "
            f"(content_pixels < {ENTRY_MIN_TEXT_PX} in {ENTRY_TEXT_BAND})"
        )
    ctx.step(f"pose image selected via the dialog: {POSE_IMAGE}")

    baseline = app.capture()
    app.click(*GENERATE_BUTTON)
    # step 2: the first log line is 1-2 px tall (Consolas 9pt) and can land
    # between the step-4 sample rows — measured live 2026-08-19, it renders
    # at y 543-549 while the old grid only sampled 540/544/548 (missed it).
    app.wait_region_change(
        baseline, STATUS_BOX, min_changed=15, timeout=TRANSITION_WAIT_S, step=2
    )
    ctx.step("progress transition: generation started (SF3D completion NOT asserted)")

    ctx.shot("SF3D generation started")

    viewer = wait_for_window(
        VIEWER_TITLE, timeout_s=VIEWER_WAIT_S, budget_s=ctx.budget_s
    )
    if viewer is None:
        raise TesterAssertionError(
            f"viewer window ({VIEWER_TITLE!r}) never appeared within "
            f"{VIEWER_WAIT_S}s — generation did not complete"
        )
    ctx.desktop = viewer
    ctx.step("viewer window appeared: generation completed, scene loading")
    time.sleep(VIEWER_SETTLE_S)
    ctx.shot("AG viewer with the generated character")


FEATURES = [
    Feature(
        name="AG GUI generation start",
        description=(
            "Attach to the AG tkinter GUI (launched by the tester), verify "
            "the layout signature (tabs / bottom bar / status widget), load "
            "a real pose via the native file dialog (driven by keystrokes), "
            "click Generate Character and assert the progress state "
            "transition only (status region repaint) — SF3D completion is "
            "not asserted via text; instead the feature waits for the "
            "viewer window the app spawns at the end of a successful "
            "export and screenshots the generated character's 3D scene. "
            "Tk exposes no "
            "accessibility tree on this machine, so clicks are measured "
            "physical input; a busy desktop that withholds foreground is an "
            "honest env error."
        ),
        run=run,
        native=True,
        budget_s=900,
    )
]
