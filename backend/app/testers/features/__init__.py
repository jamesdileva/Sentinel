"""UI click-through features — Playwright-driven feature verification
(docs/clickthrough_plan.md, v1.17.14.0; Electron engine v1.17.14.4;
native engine v1.17.16.0).

Each module exposes `FEATURES = [Feature(...), ...]`; the registry maps
project slug to its list. Features run after a project's smoke tester
passes (TesterRunner hook) — same user-initiated flow (Rule 2), scripted
deterministic assertions only (Rule 3), loopback-only navigation (Rule 1).

Three engines, chosen per feature: browser features drive the system Edge
via Playwright; Electron features (`electron=True`) drive the project's
packaged desktop app window via the CDP-attached FeatureRunner (packaged
exe launched with a `--user-data-dir` sandbox, see feature_runner.py);
native features (`native=True`, v1.17.16.0) drive the project's own
tkinter window via pywinauto (UIA) — DesktopApp attach by title, guarded
so only the declared window is ever driven (desktop_runner.py).
"""

from dataclasses import dataclass
from typing import Callable

from app.testers.features._context import FeatureContext

__all__ = ["FEATURES", "Feature", "FeatureContext"]


@dataclass(frozen=True)
class Feature:
    """A named UI click-through for one project (docs/clickthrough_plan.md).

    `run(ctx)` receives a FeatureContext with a Playwright page; steps
    record checkpoints and screenshots into the same tester session.

    `electron=True` switches the engine: the feature drives the project's
    packaged desktop app window (CDP-attached, sandboxed `--user-data-dir`)
    instead of a fresh Edge tab — `ctx.go()` is refused for such features
    because the window is already on the app (v1.17.14.4).
    `native=True` (v1.17.16.0) switches to the pywinauto engine: the
    feature drives the project's own tkinter window (DesktopApp attach by
    title) — `ctx.desktop` replaces `ctx.page`, `ctx.go()` is refused.
    `budget_s` overrides the 120 s per-feature deadline (v1.17.14.4).
    """

    name: str
    description: str
    run: Callable[[FeatureContext], None]
    electron: bool = False
    native: bool = False
    budget_s: int = 120


# Submodules import `Feature` back from this package (circular-safe,
# same pattern as the testers registry).
from app.testers.features import (  # noqa: E402
    ag,
    airadio,
    algo_trader,
    card_game,
    cg,
    demake,
    dinner_menu,
    hft_order_book,
    tv_scheduler,
    workflow_toolkit,
)


def _build_registry() -> dict[str, list[Feature]]:
    return {
        "Ag": ag.FEATURES,
        "Airadio": airadio.FEATURES,
        "Algo-Trader": algo_trader.FEATURES,
        "Card-Game": card_game.FEATURES,
        "Cg": cg.FEATURES,
        "Demake-Engine": demake.FEATURES,
        "Dinner-Menu-Generator": dinner_menu.FEATURES,
        "Hft-Order-Book": hft_order_book.FEATURES,
        "Tv-Scheduler": tv_scheduler.FEATURES,
        "Workflow-Toolkit": workflow_toolkit.FEATURES,
    }


FEATURES: dict[str, list[Feature]] = _build_registry()
