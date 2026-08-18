"""Dinner Menu Generator click-through features (docs/clickthrough_plan.md).

Locator ground truth (2026-08-17, UI scan): header action buttons
(`＋ Add Meal`, `💡 Suggest Meal`, `🧠 AI On/Off`, theme toggle), add-meal
modal (inputs `Meal name` / `Ingredients (comma separated)`, submit
`Add Meal`), ManageMeals list (tabs Meals/Snacks/Staples, `Search meals…`,
per-row `Edit`/`Delete`, delete shows an undo bar with `Undo` / `×`). The
`💡 Suggest Meal` feature calls Ollama — not exercised (Rule 3: no LLM
coupling in Sentinel's feature layer).

Live ground truth (2026-08-18): the theme toggle button label does NOT
re-render on click (`toggleTheme` writes `data-theme` on `#root` directly,
no React state change), so the label is stale until the next render. The
feature must locate the button by its stable `title="Toggle dark / light"`
and assert the `#root[data-theme]` attribute, never the label.

The features create a uniquely-named meal and delete it again, so the
app's real DB is left exactly as it was (plan: destructive actions only
against self-created entities). The theme toggle returns to the theme it
started in.
"""

import time

from app.testers._helpers import TesterAssertionError
from app.testers.features import Feature, FeatureContext

APP_URL = "http://localhost:5173"  # vite 8 binds ::1 — localhost, not 127.0.0.1

_THEME_JS = "document.getElementById('root')" ".getAttribute('data-theme') === '%s'"


def _add_meal(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)
    name = f"feature-meal-{time.time_ns()}"
    page.get_by_role("button", name="＋ Add Meal").click()
    page.get_by_placeholder("Meal name").fill(name)
    page.get_by_placeholder("Ingredients (comma separated)").fill("one, two, three")
    page.get_by_role("button", name="Add Meal", exact=True).click()
    ctx.step("submitted add-meal modal")

    page.get_by_placeholder("Search meals…").fill(name)
    page.get_by_text(name, exact=True).first.wait_for(state="visible", timeout=15000)
    ctx.step("meal appears in the meals list")
    ctx.shot("meal added via modal")

    page.get_by_role("button", name="Delete", exact=True).click()
    page.get_by_text(name, exact=True).first.wait_for(state="hidden", timeout=15000)
    page.get_by_role("button", name="×").click()
    ctx.step("self-created meal deleted, undo bar dismissed")
    ctx.shot("meals list after cleanup")


def _toggle_theme(ctx: FeatureContext) -> None:
    page = ctx.page
    ctx.go(APP_URL)
    root = page.locator("#root")
    initial = root.get_attribute("data-theme")
    if initial not in ("dark", "light"):
        raise TesterAssertionError(f"unexpected initial theme: {initial!r}")
    target = "dark" if initial == "light" else "light"

    toggle = page.locator('button[title="Toggle dark / light"]')
    toggle.click()
    page.wait_for_function(_THEME_JS % target)
    ctx.step(f"theme toggled to {target}")
    ctx.shot(f"theme {target}")

    toggle.click()
    page.wait_for_function(_THEME_JS % initial)
    ctx.step(f"theme toggled back to {initial}")
    ctx.shot("theme toggle round-trip")


FEATURES = [
    Feature(
        "add meal appears in list",
        "Open the add-meal modal, submit a fresh meal, see it in the meals "
        "list, then delete it again (self-created entity only).",
        _add_meal,
    ),
    Feature(
        "dark/light theme toggle",
        "Toggle the theme twice via the header button (stable title "
        "locator — the label does not re-render); assert #root[data-theme] "
        "flips each way and ends where it started.",
        _toggle_theme,
    ),
]
