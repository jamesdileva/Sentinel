"""TV-Scheduler click-through features (docs/clickthrough_plan.md).

Locator ground truth (2026-08-17 UI scan; corrected 2026-08-18 live runs):
the SPA (frontend/src/App.jsx) is a single component. The `My Shows`
section (cardStyle, maxHeight 40vh) holds the add-show form
(`placeholder="Paste show name from open tabs..."` + `+ Add Show` submit),
the `Search saved shows...` box, and watchlist rows — each row is a div
with a direct-child `<strong>{showName}</strong>` and per-row `Expand` /
`Delete` buttons. Below it: `Popular Shows` (flex row, `overflowX: auto`,
140px cards with a `Save` button) and the 3-day `Episode Schedule`
(yesterday / today / tomorrow h3 day sections) at the bottom.

The app resolves names against TVMaze by design (latest episode + details)
and blocks duplicate adds — the feature therefore adds a REAL show from a
candidate list, skipping any already in the watchlist, then deletes it
again (plan: destructive actions only against self-created entities).
Popular shows and the schedule proxy TVMaze, so the exploration feature
fails honestly when TVMaze is down. The tester phase drives the dev stack
(it taskkills the auto-launched packaged app first), so the current
server.js/App.jsx code is exercised.
"""

import re

from app.testers._helpers import TesterAssertionError, TesterTimeoutError
from app.testers.features import Feature, FeatureContext

APP_URL = "http://localhost:5173"  # vite 8 binds ::1 — localhost, not 127.0.0.1

CANDIDATES = [
    "Chicago Fire",
    "The Expanse",
    "Futurama",
    "The Office (US)",
    "Breaking Bad",
]


def _add_and_remove_real_show(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)
    my_shows = page.locator(
        "xpath=//section[.//button[normalize-space()='+ Add Show']]"
    )
    existing = {
        name.strip() for name in my_shows.locator("xpath=.//strong").all_inner_texts()
    }
    candidate = next((c for c in CANDIDATES if c not in existing), None)
    if candidate is None:
        raise TesterAssertionError(
            f"all candidates already in the watchlist: {CANDIDATES}"
        )

    page.get_by_placeholder("Paste show name from open tabs...").fill(candidate)
    page.get_by_role("button", name="+ Add Show").click()
    ctx.step(f"submitted add-show form ({candidate})")

    row = my_shows.locator(
        f"xpath=.//div[./strong[normalize-space()='{candidate}']]"
    ).first
    row.wait_for(state="visible", timeout=15000)
    ctx.step(f"show row appears in My Shows ({candidate})")
    ctx.shot("show added to watchlist")

    row.get_by_role("button", name="Delete", exact=True).click()
    row.wait_for(state="hidden", timeout=15000)
    ctx.step("self-created show deleted")
    ctx.shot("watchlist after cleanup")


def _dashboard_scroll_exploration(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)
    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
    schedule = page.get_by_role("heading", name=re.compile("Episode Schedule")).first
    schedule.wait_for(state="visible", timeout=15000)
    day = page.locator("h3").first
    day.wait_for(state="visible", timeout=15000)
    ctx.step("3-day episode schedule at the bottom of the page")
    ctx.shot("episode schedule (3-day)")

    popular = page.get_by_role("heading", name=re.compile("Popular Shows")).first
    popular.wait_for(state="visible", timeout=15000)
    row = popular.locator("xpath=..").locator("div").first
    scrollable = row.evaluate(
        "el => { el.scrollLeft = el.scrollWidth; "
        "return el.scrollWidth > el.clientWidth; }"
    )
    if not scrollable:
        raise TesterTimeoutError("popular shows row has no horizontal overflow")
    ctx.step("popular shows row side-scrolled")
    ctx.shot("popular shows side-scroller")


def _search_filters_watchlist(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)
    page.get_by_placeholder("Search saved shows...").fill("Fire")
    ctx.step("search filter applied (matches 'Chicago Fire' when saved)")
    page.wait_for_timeout(1000)
    ctx.shot("watchlist filtered by search")


FEATURES = [
    Feature(
        "add a real show to the watchlist",
        "Add a real TVMaze-resolvable show that is not already saved, see "
        "its row in My Shows, then delete it again (self-created entity "
        "only; duplicates are skipped honestly).",
        _add_and_remove_real_show,
    ),
    Feature(
        "dashboard scroll exploration",
        "Scroll the dashboard to the bottom (3-day episode schedule), then "
        "side-scroll the Popular Shows row and capture both.",
        _dashboard_scroll_exploration,
    ),
    Feature(
        "search filters saved shows",
        "Type into the saved-shows search box and capture the filtered list.",
        _search_filters_watchlist,
    ),
]
