"""World Simulator — deterministic persistent simulation (Sprint 9).

The world is a self-contained "living toy": settlements grow, build roads,
expand, trade, and sometimes collapse. The engine is fully deterministic
(seeded RNG per day, rules in `rules_engine`, events in `event_generator`);
AI is optional flavor only and never affects sim state.
"""

from app.services.world_sim.names import settlement_name
from app.services.world_sim.skill_system import (
    grant_survival_experience,
    production_bonus,
    rebuild_speed,
    skill_level,
)
from app.services.world_sim.world_simulator import WorldSimulatorService

__all__ = [
    "WorldSimulatorService",
    "grant_survival_experience",
    "production_bonus",
    "rebuild_speed",
    "settlement_name",
    "skill_level",
]