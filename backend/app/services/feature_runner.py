"""Feature runner — executes a project's UI click-through features
(docs/clickthrough_plan.md, v1.17.14.0).

Runs after the smoke tester passes, inside the same user-initiated tester
session. Browser: the system Microsoft Edge via Playwright's msedge
channel (no browser download; consistent with headless_render). Headless
by default; SENTINEL_FEATURES_HEADED=1 opts into a visible window for
debugging.

Failure mapping (same semantics as tester_runner):
- TesterAssertionError (incl. Playwright timeouts/errors translated) -> failed
- TesterEnvError (browser launch, missing Edge, loopback guard) -> investigate
- TesterTimeoutError (feature budget) -> investigate
"""

import os

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.core.logging import get_logger
from app.services.app_sessions import _slug
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
)
from app.testers.features import FEATURES, Feature
from app.testers.features._context import FeatureContext

logger = get_logger(__name__)

DEFAULT_TIMEOUT_MS = 15_000
VIEWPORT = {"width": 1280, "height": 800}


def _headed() -> bool:
    return os.environ.get("SENTINEL_FEATURES_HEADED", "").strip() not in ("", "0")


class FeatureRunner:
    """One responsibility: resolve + run a project's click-through features."""

    def __init__(self, session):
        self.session = session

    def resolve(self, project) -> list[Feature]:
        return FEATURES.get(_slug(project.name), [])

    def describe(self, project) -> list[dict]:
        return [
            {"name": f.name, "description": f.description}
            for f in self.resolve(project)
        ]

    def run(self, project, ctx: TesterContext, service, session_id: str) -> None:
        features = self.resolve(project)
        if not features:
            return
        try:
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(
                        channel="msedge", headless=not _headed()
                    )
                except PlaywrightError as exc:
                    raise TesterEnvError(
                        f"Feature browser launch failed: {exc}"
                    ) from exc
                page = browser.new_page(viewport=VIEWPORT)
                page.set_default_timeout(DEFAULT_TIMEOUT_MS)
                try:
                    for feature in features:
                        ctx.checkpoint(f"feature start: {feature.name}")
                        fctx = FeatureContext(project, session_id, service, ctx, page)
                        try:
                            feature.run(fctx)
                        except (PlaywrightTimeoutError, PlaywrightError) as exc:
                            raise TesterAssertionError(
                                f"feature {feature.name!r} failed: {exc}"
                            ) from exc
                        ctx.checkpoint(f"feature pass: {feature.name}")
                finally:
                    browser.close()
        except PlaywrightError as exc:
            raise TesterEnvError(f"Feature run failed: {exc}") from exc
