"""Dinner Menu Generator click-through features (docs/clickthrough_plan.md).

Locator ground truth (2026-08-17, UI scan): header action buttons
(`＋ Add Meal`, `💡 Suggest Meal`, `🧠 AI On/Off`, `☀️ Light`/`🌙 Dark`
theme toggle), add-meal modal (inputs `Meal name` / `Ingredients (comma
separated)`, submit `Add Meal`), ManageMeals list (tabs Meals/Snacks/
Staples, `Search meals…`, per-row `Edit`/`Delete`, delete shows an undo
bar with `Undo` / `×`). The `💡 Suggest Meal` feature calls Ollama — not
exercised (Rule 3: no LLM coupling in Sentinel's feature layer).

The features create a uniquely-named meal and delete it again, so the
app's real DB is left exactly as it was (plan: destructive actions only
against self-created entities).
"""

import time

from app.testers.features import Feature, FeatureContext

APP_URL = "http://localhost:5173"  # vite 8 binds ::1 — localhost, not 127.0.0.1


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
    page.get_by_role("button", name="🌙 Dark").click()
    page.get_by_role("button", name="☀️ Light").wait_for(state="visible", timeout=5000)
    ctx.step("theme toggled to light")
    page.get_by_role("button", name="☀️ Light").click()
    page.get_by_role("button", name="🌙 Dark").wait_for(state="visible", timeout=5000)
    ctx.step("theme toggled back to dark")
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
        "Toggle the theme twice; the toggle button label flips each way.",
        _toggle_theme,
    ),
]
