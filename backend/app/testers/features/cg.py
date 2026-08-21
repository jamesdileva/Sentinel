"""Cg click-through features (docs/clickthrough_plan.md).

Locator ground truth (2026-08-17 UI scan; corrected 2026-08-18 live runs):
- Dashboard: topic-count input (`id="topic-count"`), four style buttons
  (`Standard` / `Weird History` / `True Crime` / `Mysteries`), and a
  `Pipeline Status` card whose `Total Topics` stat renders as
  `<span class="stat-value">` — a live run proved the scan's
  `div.stat-value` was wrong (span, not div).
- Nav (App.tsx): `.nav-link` links `Dashboard` / `Topics` / `Research` /
  `Scripts` / `Production` / `Publish` / `Analytics`.
- Topics page (pages/Topics.tsx): `.topic-card` rows with an
  `.topic-header` h3 title + `.status-badge`; `Pending Review` cards are
  DISCOVERED and get an `Approve` button; `Approved` cards get
  `Run Research` (btn-outline). Mock generate always inserts DISCOVERED
  rows (api/topics.py), so fresh pending cards exist after dashboard
  generation.
- Research page (pages/Research.tsx): `#topic-select` lists every
  researchable topic (`APPROVED` / `RESEARCHING` / `RESEARCH_COMPLETE` /
  `SCRIPT_DRAFTED`) and auto-selects the first.

The backend runs with `LLM_PROVIDER=mock` (pinned by the tester), so topic
generation is deterministic. Research launches a background scrape job
(network-bound, non-deterministic) — the feature asserts the RESEARCHING
transition started (or already finished), never completion. The tester
already generates mock topics on every run, so the residue of one more
deterministic topic plus an in-flight research job is the status quo — no
cleanup needed.
"""

import re

from app.testers._helpers import TesterAssertionError, TesterTimeoutError
from app.testers.features import Feature, FeatureContext

APP_URL = "http://localhost:5173"  # renderer vite dev (tester's electron-dev)


def _studio_round_trip(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)
    page.locator("#topic-count").fill("2")
    page.get_by_role("button", name="Standard", exact=True).click()
    ctx.step("clicked generate topics (Standard, 2)")

    status_card = page.get_by_text("Pipeline Status", exact=True)
    status_card.first.wait_for(state="visible", timeout=30000)
    stat = page.locator("span.stat-value", has_text=re.compile(r"^\s*\d"))
    stat.first.wait_for(state="visible", timeout=15000)
    # v1.17.18.5 (audit2 T7 + cg int("") guard): a stat rendering no digits
    # raised a raw ValueError outside the Tester error taxonomy.
    digits = re.sub(r"\D", "", stat.first.inner_text())
    if not digits:
        raise TesterAssertionError("Total Topics stat rendered without a number")
    count = int(digits)
    if count < 1:
        raise TesterAssertionError(f"Total Topics stat shows {count}")
    ctx.step(f"topics generated and rendered (Total Topics = {count})")
    ctx.shot("dashboard after topic generation")

    page.get_by_role("link", name="Topics", exact=True).click()
    pending = page.locator(
        ".topic-card", has=page.locator(".status-badge", has_text="DISCOVERED")
    ).first
    pending.wait_for(state="visible", timeout=15000)
    ctx.step("topics page shows pending review cards")
    title = pending.locator("h3").first.inner_text().strip()
    ctx.shot("topics page (pending review)")

    pending.get_by_role("button", name="Approve", exact=True).click()
    approved = page.locator(".topic-card.approved", has_text=title).first
    approved.wait_for(state="visible", timeout=15000)
    ctx.step(f"approved topic: {title}")
    ctx.shot("topics page (approved)")

    approved.get_by_role("button", name="Run Research", exact=True).click()
    page.wait_for_function(
        "() => { const el = document.querySelector('.topic-card.approved "
        ".status-badge'); return el && (el.textContent.includes('RESEARCHING') "
        "|| el.textContent.includes('RESEARCH COMPLETE')); }",
        timeout=20000,
    )
    ctx.step(f"research started on {title}")
    ctx.shot("research in progress (topics page)")

    page.get_by_role("link", name="Research", exact=True).click()
    page.wait_for_function(
        "() => { const sel = document.getElementById('topic-select'); "
        "return sel && sel.options.length > 1; }",
        timeout=15000,
    )
    found = page.evaluate(
        "(t) => { const sel = document.getElementById('topic-select'); "
        "return sel && Array.from(sel.options).some(o => o.textContent === t); }",
        title,
    )
    if not found:
        raise TesterTimeoutError(f"topic '{title}' not researchable on Research tab")
    ctx.step(f"research tab lists {title}")
    ctx.shot("research viewer")


FEATURES = [
    Feature(
        "studio round-trip: generate, approve, research",
        "Generate topics on the Dashboard, approve a pending topic, run "
        "research on it, then open the Research tab and confirm the topic "
        "is listed (mock LLM — deterministic generation; research runs its "
        "background scrape, only the transition is asserted).",
        _studio_round_trip,
    ),
]
