"""Cg click-through features (docs/clickthrough_plan.md).

Locator ground truth (2026-08-17 UI scan, corrected 2026-08-18 live run):
the renderer (Vite dev on :5173 via the tester's `electron-dev` launch)
has a Dashboard with the topic-count input (`id="topic-count"`,
`htmlFor="topic-count"` label) and four style buttons (`Standard` /
`Weird History` / `True Crime` / `Mysteries`); after generating, a
`Pipeline Status` card shows the `Total Topics` stat. The stats render as
`<span className="stat-value">` — the live run proved the scan's
`div.stat-value` was wrong (span, not div). The backend runs with
`LLM_PROVIDER=mock` (pinned by the tester) so topic generation is
deterministic (fixed MOCK_TOPICS list).

The tester already generates mock topics on every run, so the residue of
one more deterministic topic is the status quo — no cleanup needed.
"""

import re

from app.testers._helpers import TesterTimeoutError
from app.testers.features import Feature, FeatureContext

APP_URL = "http://localhost:5173"  # renderer vite dev (tester's electron-dev)


def _generate_topics(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)
    page.locator("#topic-count").fill("2")
    page.get_by_role("button", name="Standard", exact=True).click()
    ctx.step("clicked generate topics (Standard, 2)")

    status_card = page.get_by_text("Pipeline Status", exact=True)
    status_card.first.wait_for(state="visible", timeout=30000)
    stat = page.locator("span.stat-value", has_text=re.compile(r"^\s*\d"))
    stat.first.wait_for(state="visible", timeout=15000)
    count = int(re.sub(r"\D", "", stat.first.inner_text()))
    if count < 1:
        raise TesterTimeoutError(f"Total Topics stat shows {count}")
    ctx.step(f"topics generated and rendered (Total Topics = {count})")
    ctx.shot("dashboard after topic generation")


FEATURES = [
    Feature(
        "generate topics from dashboard",
        "Set the topic count, click Standard, and verify the Pipeline "
        "Status card reports the generated topics (mock LLM — "
        "deterministic).",
        _generate_topics,
    ),
]
