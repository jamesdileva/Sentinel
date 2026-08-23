"""Scripted testers — per-app deterministic verification scripts
(later.md Tier 2, docs/tier2_plan.md).

Each module exposes `TESTER = Tester(...)`; the registry maps project slug
(`_slug(project.name)`) to its tester. `DEFAULT_SMOKE` is the fallback for
launchable apps without a custom tester. Testers run only when the user
clicks "Run tester" (Rule 2) and never call AI (Rule 3).

App-specific facts live here (ports, routes, env gaps) — see the plan doc.
"""

from dataclasses import dataclass
from typing import Callable

from app.testers._helpers import TesterContext

__all__ = ["DEFAULT_SMOKE", "TESTERS", "Tester", "TesterContext"]


@dataclass(frozen=True)
class Tester:
    """A named runnable tester for one project (or the default smoke).

    v1.17.13.4: `web_url` / `extra_launch` / `ports` — the app facts
    build->open needs to actually open a browser-served app: the URL to open
    in the default browser, the servers the stored startup does not cover
    (each launched detached after it), and the ports to free first so the
    fresh instance binds them (restart semantics, no drift orphans).
    v1.17.13.5: `auto_launch` — the tester runner launches the project's
    packaged desktop app (win-unpacked/tauri layouts) before the run and
    captures its window, with no per-tester code; set False to opt out.
    """

    name: str
    description: str
    run: Callable[[TesterContext], None]
    project_slug: str | None = None  # None = default smoke (any launchable app)
    kind: str = "custom"
    web_url: str | None = None  # browser-served app: opened after launch
    extra_launch: tuple[str, ...] = ()  # non-stored servers to start too
    ports: tuple[int, ...] = ()  # app ports freed before launching
    auto_launch: bool = True  # runner auto-launches the packaged app


# Submodules import `Tester` back from this package, so they load only after
# the class above exists (circular-safe, noqa: E402).
from app.testers import (  # noqa: E402
    ag,
    algo_trader,
    card_game,
    career_os,
    cg,
    default_smoke,
    demake_engine,
    dinner_menu_generator,
    finsight,
    hft_order_book,
    tv_scheduler,
    workflow_toolkit,
)


def _build_registry() -> dict[str, Tester]:
    testers = [
        ag.TESTER,
        algo_trader.TESTER,
        card_game.TESTER,
        career_os.TESTER,
        cg.TESTER,
        demake_engine.TESTER,
        dinner_menu_generator.TESTER,
        finsight.TESTER,
        hft_order_book.TESTER,
        tv_scheduler.TESTER,
        workflow_toolkit.TESTER,
    ]
    registry = {t.project_slug: t for t in testers if t.project_slug}
    return registry


TESTERS: dict[str, Tester] = _build_registry()
DEFAULT_SMOKE: Tester = default_smoke.TESTER
