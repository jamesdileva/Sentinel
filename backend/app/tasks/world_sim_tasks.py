"""World Simulator task — beat-driven advancement (Sprint 9, docs/02 §11.6).

The in-process scheduler calls `world_sim_tick` every `world_sim_tick_seconds`;
catch_up advances ~time_scale days per interval while running and bounded
catch-up after downtime, so the world keeps time with the clock.
"""

from app.core.logging import get_logger
from app.services.world_sim import WorldSimulatorService

logger = get_logger(__name__)


def world_sim_tick() -> dict:
    """Advance the world to reflect elapsed real time (bounded catch-up)."""
    days = WorldSimulatorService().catch_up()
    logger.info("world tick advanced %d day(s)", days)
    return {"days_advanced": days}
