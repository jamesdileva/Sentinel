"""UI click-through features — Playwright-driven feature verification
(docs/clickthrough_plan.md, v1.17.14.0).

Each module exposes `FEATURES = [Feature(...), ...]`; the registry maps
project slug to its list. Features run after a project's smoke tester
passes (TesterRunner hook) — same user-initiated flow (Rule 2), scripted
deterministic assertions only (Rule 3), loopback-only navigation (Rule 1).
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
    """

    name: str
    description: str
    run: Callable[[FeatureContext], None]


# Submodules import `Feature` back from this package (circular-safe,
# same pattern as the testers registry).
from app.testers.features import (  # noqa: E402
    card_game,
    cg,
    demake,
    dinner_menu,
    tv_scheduler,
)


def _build_registry() -> dict[str, list[Feature]]:
    return {
        "Card-Game": card_game.FEATURES,
        "Cg": cg.FEATURES,
        "Demake-Engine": demake.FEATURES,
        "Dinner-Menu-Generator": dinner_menu.FEATURES,
        "Tv-Scheduler": tv_scheduler.FEATURES,
    }


FEATURES: dict[str, list[Feature]] = _build_registry()
