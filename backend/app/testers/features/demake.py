"""Demake Engine click-through features (docs/clickthrough_plan.md).

Locator ground truth (2026-08-17, UI scan): frontend/index.html is plain
DOM — `#file-input` (hidden, accept .mp4), `#drop-zone`, `#upload-btn`
("◆ GENERATE DEMAKE ◆", disabled until a file is chosen), `#status-text`
(starts "INITIALIZING..."), `#progress-section`, `#check-btn`
("◆ CHECK IF READY ◆" after 30 s), `#play-link` ("▶ PLAY YOUR DEMAKE").

Scope: the REST tester already runs the full pipeline to `ready`
(upload -> VLM -> sprites -> manifest). This feature proves the UI wiring
only — pick the repo's own fixture via the file input, submit, and assert
the pipeline starts (status leaves INITIALIZING). The Phaser game page is
canvas — the DOM boundary is the feature boundary.
"""

import time
from pathlib import Path

from app.testers._helpers import (
    TesterAssertionError,
    TesterEnvError,
    TesterTimeoutError,
)
from app.testers.features import Feature, FeatureContext

APP_URL = "http://127.0.0.1:8000"
POLL_S = 2
MAX_WAIT_S = 60


def _upload_starts_pipeline(ctx: FeatureContext) -> None:
    page = ctx.page
    fixture = Path(ctx.project.path) / "backend" / "test_game_trailer.mp4"
    if not fixture.exists():
        raise TesterEnvError(f"Upload fixture missing: {fixture}")

    ctx.go(APP_URL)
    upload = page.locator("#upload-btn")
    if upload.is_enabled():
        # v1.17.18.5 (audit2 T7): UI-state assertions, not env failures.
        raise TesterAssertionError("upload button should start disabled")
    page.set_input_files("#file-input", str(fixture))
    upload.wait_for(state="visible", timeout=10000)
    if not upload.is_enabled():
        raise TesterAssertionError("upload button did not enable after choosing a file")
    ctx.step("fixture chosen — generate button enabled")

    upload.click()
    ctx.step("submitted upload via UI")

    status = page.locator("#status-text")
    status.first.wait_for(state="visible", timeout=10000)

    deadline = time.time() + MAX_WAIT_S
    while time.time() < deadline:
        text = status.first.inner_text()
        if text and "INITIALIZING" not in text:
            break
        page.wait_for_timeout(POLL_S * 1000)
    text = status.first.inner_text()
    if not text or "INITIALIZING" in text:
        raise TesterTimeoutError(
            f"pipeline did not leave INITIALIZING within {MAX_WAIT_S}s"
        )
    ctx.step(f"pipeline running via UI ({text})")
    ctx.shot("pipeline progress after UI upload")


FEATURES = [
    Feature(
        "upload starts the pipeline via the UI",
        "Pick the repo's test trailer in the drop zone, click GENERATE, "
        "and verify the status text leaves INITIALIZING (deep pipeline "
        "correctness is the REST tester's job).",
        _upload_starts_pipeline,
    ),
]
