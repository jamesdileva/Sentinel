"""TV-Scheduler click-through features (docs/clickthrough_plan.md).

Phase 2 (v1.17.14.4): the features drive the PACKAGED app's real window —
the FeatureRunner relaunches the sandboxed exe (CDP-attached) and the
window is already on the app, so there is no `ctx.go()` (electron features
are refused navigation). The packaged asar still ships the same App.jsx
DOM as the dev stack did, so the locator ground truth below is unchanged.

Locator ground truth (2026-08-17 UI scan; corrected 2026-08-18 live runs):
the SPA (frontend/src/App.jsx) is a single component. The `My Shows`
section (cardStyle, maxHeight 40vh) holds the add-show form
(`placeholder="Paste show name from open tabs..."` + `+ Add Show` submit),
the `Search saved shows...` box, and watchlist rows — each row is a div
with a direct-child `<strong>{showName}</strong>` and per-row `Expand` /
`Delete` buttons. Below it: `Popular Shows` (flex row, `overflowX: auto`,
140px cards with a `Save` button) and the 3-day `Episode Schedule`
(yesterday / today / tomorrow h3 day sections) at the bottom. The schedule
grid (`gridTemplateColumns: 1fr 1fr 1fr`) only renders once the TVMaze
fetch settles (`!loading && !error`); each day section holds episode rows
— divs with a `Save to My Shows` button — so a loaded day is detectable by
that row (a 2026-08-18 live run scrolled before the fetch resolved: the
page was short, `scrollTo` did nothing, and the screenshot showed an
unloaded schedule — the feature now waits for a loaded episode row and
proves `scrollY > 0`).

The app resolves names against TVMaze by design (latest episode + details)
and blocks duplicate adds — the feature therefore adds a REAL show from a
candidate list, skipping any already in the watchlist, then deletes it
again (plan: destructive actions only against self-created entities).
Popular shows and the schedule proxy TVMaze, so the exploration feature
fails honestly when TVMaze is down. The sandboxed instance starts with a
fresh userData DB, so the watchlist is empty and the add/delete round trip
is self-contained.
"""

import re

from app.testers._helpers import TesterAssertionError
from app.testers.features import Feature, FeatureContext

CANDIDATES = [
    "Chicago Fire",
    "The Expanse",
    "Futurama",
    "The Office (US)",
    "Breaking Bad",
]


def _add_and_remove_real_show(ctx: FeatureContext) -> None:
    page = ctx.page
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
    episode_row = page.locator(
        "xpath=//section[.//h3]//div"
        "[.//button[normalize-space()='Save to My Shows']]"
    ).first
    episode_row.wait_for(state="visible", timeout=45000)
    ctx.step("3-day episode schedule loaded (TVMaze fetch settled)")

    scrolled = page.evaluate(
        "() => { window.scrollTo(0, document.body.scrollHeight); "
        "return window.scrollY > 0; }"
    )
    if not scrolled:
        # v1.17.18.5 (audit2 T7): assertion failure, not a timeout.
        raise TesterAssertionError("page content fits without scrolling")
    day = page.locator("h3").first
    day.wait_for(state="visible", timeout=15000)
    ctx.step("scrolled to the bottom — episode schedule in view")
    ctx.shot("episode schedule (3-day)")

    popular = page.get_by_role("heading", name=re.compile("Popular Shows")).first
    popular.wait_for(state="visible", timeout=15000)
    row = popular.locator("xpath=..").locator("div").first
    scrollable = row.evaluate(
        "el => { el.scrollLeft = el.scrollWidth; "
        "return el.scrollWidth > el.clientWidth; }"
    )
    if not scrollable:
        raise TesterAssertionError("popular shows row has no horizontal overflow")
    ctx.step("popular shows row side-scrolled")
    ctx.shot("popular shows side-scroller")


def _search_filters_watchlist(ctx: FeatureContext) -> None:
    """v1.17.18.5 (audit2 T6): the old version typed text and screenshotted —
    green regardless of whether filtering worked (Rule 6). Now it adds a
    self-created show first, asserts the filter KEEPS the matching row
    visible while hiding nothing else relevant, then cleans up."""
    page = ctx.page
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
    row = my_shows.locator(
        f"xpath=.//div[./strong[normalize-space()='{candidate}']]"
    ).first
    row.wait_for(state="visible", timeout=15000)

    search = page.get_by_placeholder("Search saved shows...")
    # Case-mismatch on purpose: proves the filter matches content, and that
    # the row SURVIVES filtering (a broken filter would hide it).
    search.fill(candidate.upper())
    page.wait_for_timeout(1000)
    if row.count() < 1:
        raise TesterAssertionError(
            f"search '{candidate.upper()}' hid the matching row ({candidate})"
        )
    ctx.step(f"search filter keeps the matching row ('{candidate}' via upper-case)")
    ctx.shot("watchlist filtered by search")

    # Cleanup: only the self-created entity is touched.
    search.fill("")
    page.wait_for_timeout(500)
    row.get_by_role("button", name="Delete", exact=True).click()
    row.wait_for(state="hidden", timeout=15000)
    ctx.step("self-created show deleted after filter check")


FEATURES = [
    Feature(
        "add a real show to the watchlist",
        "Add a real TVMaze-resolvable show that is not already saved, see "
        "its row in My Shows, then delete it again (self-created entity "
        "only; duplicates are skipped honestly).",
        _add_and_remove_real_show,
        electron=True,
    ),
    Feature(
        "dashboard scroll exploration",
        "Scroll the dashboard to the bottom (3-day episode schedule), then "
        "side-scroll the Popular Shows row and capture both.",
        _dashboard_scroll_exploration,
        electron=True,
    ),
    Feature(
        "search filters saved shows",
        "Add a self-created show, type its name in upper case into the "
        "saved-shows search box, and assert the matching row stays visible "
        "(filtering proven, not just screenshotted), then delete it.",
        _search_filters_watchlist,
        electron=True,
    ),
]
