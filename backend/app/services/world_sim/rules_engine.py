"""Pure deterministic rules for the world simulation (docs/02 §11.2).

No I/O here — just calculations over `SettlementState` and the world seed.
Terrain is a deterministic function of (x, y, seed) so a given seed always
renders the same map without storing a grid.
"""

import random
from dataclasses import dataclass, field

from app.services.world_sim.skill_system import production_bonus

TERRAIN_PLAINS = "plains"
TERRAIN_FOREST = "forest"
TERRAIN_HILLS = "hills"
TERRAIN_MOUNTAINS = "mountains"
TERRAIN_WATER = "water"

TERRAIN_TYPES = (
    TERRAIN_PLAINS,
    TERRAIN_FOREST,
    TERRAIN_HILLS,
    TERRAIN_MOUNTAINS,
    TERRAIN_WATER,
)

# How much each terrain feeds a farmer (multiplier on base yield).
TERRAIN_FERTILITY = {
    TERRAIN_PLAINS: 1.1,
    TERRAIN_FOREST: 0.9,
    TERRAIN_HILLS: 0.7,
    TERRAIN_MOUNTAINS: 0.4,
    TERRAIN_WATER: 0.1,
}

# Expansion thresholds and costs (documented, tune-with-tests).
EXPAND_POPULATION = 600
EXPAND_LEVEL = 3
EXPAND_CHANCE = 0.25
FOUNDING_POPULATION = 200
LEVEL_COST_BASE = 100
TRADE_BONUS_FRACTION = 0.06
RAID_CHANCE = 0.02
RAID_DISTANCE = 3
DISCOVERY_CHANCE = 0.04
DISCOVERY_EXPLORER_BONUS = 0.01
SOCIAL_CHANCE = 0.03

DISASTER_FLOOD = "flood"
DISASTER_DROUGHT = "drought"
DISASTER_PLAGUE = "plague"
DISASTER_TYPES = (DISASTER_FLOOD, DISASTER_DROUGHT, DISASTER_PLAGUE)

# Base per-day disaster probability (terrain may raise it).
DISASTER_BASE_CHANCE = {
    DISASTER_FLOOD: 0.015,
    DISASTER_DROUGHT: 0.010,
    DISASTER_PLAGUE: 0.008,
}

TERRAIN_DISASTER_MODIFIER = {
    TERRAIN_PLAINS: {DISASTER_FLOOD: 1.3, DISASTER_DROUGHT: 1.0, DISASTER_PLAGUE: 1.2},
    TERRAIN_FOREST: {DISASTER_FLOOD: 1.0, DISASTER_DROUGHT: 0.6, DISASTER_PLAGUE: 1.0},
    TERRAIN_HILLS: {DISASTER_FLOOD: 0.7, DISASTER_DROUGHT: 1.4, DISASTER_PLAGUE: 0.9},
    TERRAIN_MOUNTAINS: {DISASTER_FLOOD: 0.4, DISASTER_DROUGHT: 2.0, DISASTER_PLAGUE: 0.7},
    TERRAIN_WATER: {DISASTER_FLOOD: 1.0, DISASTER_DROUGHT: 1.0, DISASTER_PLAGUE: 1.0},
}


@dataclass
class SettlementState:
    id: str
    name: str
    x: int
    y: int
    population: int
    food: int
    level: int = 1
    experience: int = 0
    status: str = "active"  # "active" | "abandoned"
    founded_day: int = 0
    destroyed_day: int | None = None
    parent_id: str | None = None
    farmers: int = 10
    builders: int = 5
    merchants: int = 2
    explorers: int = 1
    construction: int = 0

    @property
    def active(self) -> bool:
        return self.status == "active"


def _hash(x: int, y: int, seed: int) -> int:
    """Deterministic hash of a world cell (seeded)."""
    h = (x * 374761393 + y * 668265263 + seed * 1274126177) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h ^ (h >> 16)


def terrain_at(x: int, y: int, seed: int) -> str:
    """Terrain type for a cell — deterministic per world seed."""
    r = _hash(x, y, seed) / 0xFFFFFFFF
    if r < 0.10:
        return TERRAIN_MOUNTAINS
    if r < 0.24:
        return TERRAIN_WATER
    if r < 0.44:
        return TERRAIN_HILLS
    if r < 0.72:
        return TERRAIN_FOREST
    return TERRAIN_PLAINS


def fertility(x: int, y: int, seed: int) -> float:
    return TERRAIN_FERTILITY[terrain_at(x, y, seed)]


def daily_food_production(s: SettlementState, seed: int) -> int:
    """Food grown per day: farmers × 6 × terrain fertility × skill bonus."""
    base = max(s.farmers, 1) * 6
    boost = production_bonus(s.level)
    return int(base * fertility(s.x, s.y, seed) * boost)


def daily_consumption(s: SettlementState) -> int:
    """Food eaten per day: one per resident."""
    return max(s.population, 1)


def food_surplus(s: SettlementState, seed: int) -> int:
    """Production minus consumption (negative means shortfall)."""
    return daily_food_production(s, seed) - daily_consumption(s)


def construction_needed(s: SettlementState) -> int:
    """Progress required to reach the next settlement level."""
    return LEVEL_COST_BASE * s.level


def disaster_chance(terrain: str, disaster: str) -> float:
    """Daily probability of a disaster, with terrain modifier."""
    return DISASTER_BASE_CHANCE[disaster] * TERRAIN_DISASTER_MODIFIER[terrain][disaster]


def expansion_available(
    s: SettlementState,
    occupied: set[tuple[int, int]],
    rng: random.Random,
    seed: int,
) -> tuple[int, int] | None:
    """Pick a free, buildable cell for a new settlement, scanning outward.

    Returns (x, y) or None when the settlement cannot or decides not expand.
    """
    if s.population < EXPAND_POPULATION or s.level < EXPAND_LEVEL:
        return None
    if rng.random() > EXPAND_CHANCE:
        return None
    for radius in range(1, 4):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                nx, ny = s.x + dx, s.y + dy
                if terrain_at(nx, ny, seed) == TERRAIN_WATER:
                    continue
                if (nx, ny) in occupied:
                    continue
                return (nx, ny)
    return None