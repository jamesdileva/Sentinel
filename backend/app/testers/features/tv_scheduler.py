"""TV-Scheduler click-through features (docs/clickthrough_plan.md).

Locator ground truth (2026-08-17, UI scan): the SPA (frontend/src/App.jsx)
is a single component — add-show form (`placeholder="Paste show name from
open tabs..."` + `+ Add Show` submit), watchlist rows render
`<strong>{showName}</strong>` with per-row `Expand` / `Delete` buttons,
search input `Search saved shows...`, `Refresh Schedule` button.

Backend note: the packaged app (auto-launched by the tester runner) owns
:3050 and writes to the real userData DB — the feature therefore adds a
uniquely-named show and deletes it again (plan: destructive actions only
against self-created entities). The show lookup may hit an external API;
a failed lookup falls back to a `manual-<ts>` id, so the flow works
offline — the assertion is on the UI's own response.
"""

import time

from app.testers.features import Feature, FeatureContext

APP_URL = "http://localhost:5173"  # vite 8 binds ::1 — localhost, not 127.0.0.1


def _add_and_remove_show(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)
    name = f"Feature Show {time.time_ns()}"
    page.get_by_placeholder("Paste show name from open tabs...").fill(name)
    page.get_by_role("button", name="+ Add Show").click()
    ctx.step("submitted add-show form")

    row_text = page.get_by_text(name, exact=True)
    row_text.first.wait_for(state="visible", timeout=15000)
    ctx.step("show row appears in My Shows")
    ctx.shot("show added to watchlist")

    row = page.locator(f"xpath=//div[.//strong[normalize-space()='{name}']]").first
    row.get_by_role("button", name="Delete").click()
    page.get_by_text(name, exact=True).first.wait_for(state="hidden", timeout=15000)
    ctx.step("self-created show deleted")
    ctx.shot("watchlist after cleanup")


def _search_filters_watchlist(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)
    page.get_by_placeholder("Search saved shows...").fill("Feature Show")
    ctx.step("search filter applied")
    page.wait_for_timeout(1000)
    ctx.shot("watchlist filtered by search")


FEATURES = [
    Feature(
        "add show to watchlist",
        "Add a uniquely-named show via the form, see it in My Shows, then "
        "delete it again (self-created entity only).",
        _add_and_remove_show,
    ),
    Feature(
        "search filters saved shows",
        "Type into the saved-shows search box and capture the filtered list.",
        _search_filters_watchlist,
    ),
]
