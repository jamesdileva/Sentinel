"""FeatureContext — Playwright page fixture + step/shot recording for
click-through features (docs/clickthrough_plan.md, v1.17.14.0).

Wraps the tester TesterContext so features share the session, checkpoint
and screenshot plumbing. `go()` is the only sanctioned navigation: the
host must be loopback (Rule 1) — everything else is refused up front.
Electron features (v1.17.14.4) get `electron=True`: their page is the
packaged app's own window (already on the app), so `go()` is refused
entirely — the window must not be navigated away.
"""

import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
    TesterTimeoutError,
)

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}

FEATURE_BUDGET_S = 120  # default per-feature time budget
BLANK_GRAY_LEVELS = 8  # same blank threshold as render_and_register


class FeatureContext:
    """Handles handed to a feature's `run(ctx)`; one per feature, sharing
    the tester session. `page` is the Playwright sync Page (msedge tab or
    the packaged app's window for electron features)."""

    def __init__(
        self,
        project,
        session_id,
        service,
        ctx: TesterContext,
        page,
        electron: bool = False,
        budget_s: int = FEATURE_BUDGET_S,
    ):
        self.project = project
        self.session_id = session_id
        self.service = service
        self.ctx = ctx
        self.page = page
        self.electron = electron
        self.budget_s = budget_s
        self.deadline = time.monotonic() + budget_s

    # ------------------------------------------------------------ recording

    def _check_budget(self) -> None:
        if time.monotonic() > self.deadline:
            raise TesterTimeoutError(f"Feature exceeded its {self.budget_s}s budget")

    def step(self, label: str) -> None:
        self._check_budget()
        self.ctx.checkpoint(label)

    def shot(self, label: str | None = None) -> None:
        """Screenshot the current page state as a session screenshot
        (same data/screenshots/<slug>/ landing as headless renders)."""
        self._check_budget()
        tmp_name = str(
            Path(tempfile.gettempdir()) / f"sentinel-feature-{uuid.uuid4().hex}.png"
        )
        try:
            self.page.screenshot(path=tmp_name)
            with Image.open(tmp_name) as im:
                distinct = sum(1 for count in im.convert("L").histogram() if count)
            if distinct < BLANK_GRAY_LEVELS:
                raise TesterAssertionError(
                    f"feature screenshot looks blank ({label}, "
                    f"{distinct} gray levels)"
                )
            checkpoint = self.service.checkpoint(
                self.session_id, label or f"feature shot {self.ctx.steps + 1}"
            )
            self.service.register_screenshot(self.session_id, tmp_name, checkpoint.id)
        finally:
            Path(tmp_name).unlink(missing_ok=True)

    # ------------------------------------------------------------ navigation

    def go(self, url: str) -> None:
        """Loopback-guarded navigation (Rule 1): the only sanctioned way to
        move a browser-feature page. Non-loopback hosts are refused before
        any request; electron features are refused entirely — their window
        is already on the packaged app (navigating would strand it)."""
        if self.electron:
            raise TesterEnvError(
                "Feature navigation refused: electron windows are already "
                "on the packaged app (Rule 1)"
            )
        host = urlparse(url).hostname or ""
        if host not in LOOPBACK_HOSTS:
            raise TesterEnvError(
                f"Feature navigation refused: {url} is not loopback (Rule 1)"
            )
        self._check_budget()
        self.page.goto(url, wait_until="domcontentloaded")
