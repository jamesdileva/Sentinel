"""Daily simulation driver (docs/02 §11.4).

`simulate_day` applies the deterministic rules to the world: food and growth,
construction, expansion (new settlements + roads), trade, raids, discoveries,
social events, and disasters. It mutates `SettlementState` objects in place
and returns a `DayOutcome` describing what happened so the service can persist
it. All randomness comes from a per-day seeded RNG — same seed, same day,
same history.
"""

import random
from dataclasses import dataclass, field

from app.services.world_sim import names
from app.services.world_sim.rules_engine import (
    DISASTER_PLAGUE,
    DISASTER_TYPES,
    RAID_DISTANCE,
    RAID_CHANCE,
    SOCIAL_CHANCE,
    TERRAIN_DISASTER_MODIFIER,
    DISCOVERY_CHANCE,
    DISCOVERY_EXPLORER_BONUS,
    FOUNDING_POPULATION,
    SettlementState,
    construction_needed,
    daily_consumption,
    daily_food_production,
    disaster_chance,
    expansion_available,
    terrain_at,
)
from app.services.world_sim.skill_system import (
    grant_survival_experience,
    rebuild_speed,
)

MIN_ABANDON_POPULATION = 5
FAMINE_POPULATION_LOSS = 20  # 1 in N residents die each famine day
RAID_SURVIVAL_EXPERIENCE = 15
DISASTER_SEVERITY = {  # severity 1-10 by disaster type
    "flood": 6,
    "drought": 6,
    "plague": 8,
}
DISCOVERY_FOOD_BONUS = 50
GROWTH_FOOD_DIVISOR = 8
STARTING_FOOD_MULTIPLIER = 3


@dataclass
class SimEvent:
    event_type: str  # discovery | trade | conflict | natural | social
    title: str
    narrative: str
    severity: int
    affected: list[str] = field(default_factory=list)


@dataclass
class DayOutcome:
    events: list[SimEvent] = field(default_factory=list)
    new_settlements: list[SettlementState] = field(default_factory=list)
    new_roads: list[tuple[str, str]] = field(default_factory=list)


def _collapse(s: SettlementState, day: int, outcome: DayOutcome) -> None:
    s.status = "abandoned"
    s.destroyed_day = day
    outcome.events.append(
        SimEvent(
            event_type="social",
            title=f"{s.name} has collapsed",
            narrative=(
                f"{s.name} was abandoned after its people could no longer "
                "sustain themselves."
            ),
            severity=8,
            affected=[s.id],
        )
    )


def simulate_day(
    settlements: dict[str, SettlementState],
    roads: list[tuple[str, str]],
    day: int,
    seed: int,
) -> DayOutcome:
    """Advance the world by one day. Mutates settlements/roads in place."""
    rng = random.Random(f"{seed}:{day}")
    outcome = DayOutcome()
    active = [s for s in settlements.values() if s.active]

    # 1. Food, growth, famine.
    for s in active:
        produced = daily_food_production(s, seed)
        consumed = daily_consumption(s)
        surplus = produced - consumed
        if surplus >= 0:
            s.food += surplus
            s.population += max(1, surplus // GROWTH_FOOD_DIVISOR)
        else:
            s.food += surplus
            if s.food < 0:
                s.population -= max(1, s.population // FAMINE_POPULATION_LOSS)
                if s.population <= MIN_ABANDON_POPULATION:
                    s.population = 0

    # 2. Construction and level ups.
    for s in active:
        progress = int(s.builders * 0.5 * rebuild_speed(s.level))
        s.construction += progress
        if s.construction >= construction_needed(s):
            s.construction = 0
            s.level += 1
            outcome.events.append(
                SimEvent(
                    event_type="social",
                    title=f"{s.name} reached level {s.level}",
                    narrative=(
                        f"{s.name} finished its latest construction work and "
                        f"grew to level {s.level}."
                    ),
                    severity=3,
                    affected=[s.id],
                )
            )

    # 3. Expansion: found new settlements, link them with roads.
    occupied = {(s.x, s.y) for s in settlements.values() if s.active}
    for s in active:
        site = expansion_available(s, occupied, rng, seed)
        if site is None:
            continue
        nx, ny = site
        occupied.add((nx, ny))
        s.population -= FOUNDING_POPULATION
        child = SettlementState(
            id=f"set-{day}-{s.id}",
            name=names.settlement_name(rng),
            x=nx,
            y=ny,
            population=FOUNDING_POPULATION,
            food=FOUNDING_POPULATION * STARTING_FOOD_MULTIPLIER,
            founded_day=day,
            parent_id=s.id,
            farmers=18,
            builders=6,
            merchants=3,
            explorers=2,
        )
        settlements[child.id] = child
        outcome.new_settlements.append(child)
        outcome.new_roads.append((s.id, child.id))
        roads.append((s.id, child.id))
        outcome.events.append(
            SimEvent(
                event_type="discovery",
                title=f"{s.name} founded {child.name}",
                narrative=(
                    f"Explorers from {s.name} established the new settlement "
                    f"of {child.name} and a road now connects them."
                ),
                severity=4,
                affected=[s.id, child.id],
            )
        )

    # 4. Trade along roads.
    traded = []
    for a_id, b_id in list(roads):
        a, b = settlements.get(a_id), settlements.get(b_id)
        if not a or not b or not a.active or not b.active:
            continue
        if a.merchants <= 0 or b.merchants <= 0:
            continue
        a.food += int(a.food * 0.06)
        b.food += int(b.food * 0.06)
        traded.append((a.name, b.name))
    if traded and rng.random() < 0.5:
        a_name, b_name = traded[0]
        outcome.events.append(
            SimEvent(
                event_type="trade",
                title=f"Trade thrives between {a_name} and {b_name}",
                narrative=(
                    f"Merchant caravans moved goods along the roads between "
                    f"{a_name} and {b_name}, filling both granaries."
                ),
                severity=2,
            )
        )

    # 5. Raids between close settlements.
    active_list = [s for s in settlements.values() if s.active]
    for i, a in enumerate(active_list):
        for b in active_list[i + 1 :]:
            if abs(a.x - b.x) + abs(a.y - b.y) > RAID_DISTANCE:
                continue
            if not 0.5 <= a.population / max(b.population, 1) <= 2.0:
                continue
            if rng.random() >= RAID_CHANCE:
                continue
            smaller, larger = (a, b) if a.population < b.population else (b, a)
            a.population = max(0, a.population - max(1, a.population // 33))
            b.population = max(0, b.population - max(1, b.population // 33))
            smaller.population = max(0, smaller.population - max(1, smaller.population // 50))
            smaller.experience += RAID_SURVIVAL_EXPERIENCE
            larger.experience += RAID_SURVIVAL_EXPERIENCE
            outcome.events.append(
                SimEvent(
                    event_type="conflict",
                    title=f"Raid between {a.name} and {b.name}",
                    narrative=(
                        f"Warriors from {larger.name} raided {smaller.name}; "
                        "both sides counted losses."
                    ),
                    severity=6,
                    affected=[a.id, b.id],
                )
            )

    # 6. Discoveries.
    for s in active:
        chance = DISCOVERY_CHANCE + s.explorers * DISCOVERY_EXPLORER_BONUS
        if rng.random() < chance:
            s.food += DISCOVERY_FOOD_BONUS
            outcome.events.append(
                SimEvent(
                    event_type="discovery",
                    title=f"{s.name} discovered fertile land",
                    narrative=(
                        f"Scouts from {s.name} found rich, untended land nearby, "
                        f"adding {DISCOVERY_FOOD_BONUS} food to the stores."
                    ),
                    severity=2,
                    affected=[s.id],
                )
            )

    # 7. Social events.
    for s in active:
        if rng.random() < SOCIAL_CHANCE:
            gained = max(2, s.population // 25)
            s.population += gained
            outcome.events.append(
                SimEvent(
                    event_type="social",
                    title=f"{s.name} celebrated a festival",
                    narrative=(
                        f"A festival in {s.name} drew newcomers; "
                        f"population grew by {gained}."
                    ),
                    severity=2,
                    affected=[s.id],
                )
            )

    # 8. Disasters (with survival experience for the skill system).
    for s in active:
        terrain = terrain_at(s.x, s.y, seed)
        for disaster in DISASTER_TYPES:
            if rng.random() >= disaster_chance(terrain, disaster):
                continue
            pop_loss = rng.randint(10, 30)
            food_loss = rng.randint(10, 40)
            s.population = max(0, s.population - s.population * pop_loss // 100)
            s.food = max(0, s.food - s.food * food_loss // 100)
            severity = DISASTER_SEVERITY[disaster]
            if s.population <= MIN_ABANDON_POPULATION:
                s.population = 0
                _collapse(s, day, outcome)
            else:
                s.experience += grant_survival_experience(severity)
                outcome.events.append(
                    SimEvent(
                        event_type="natural",
                        title=f"A {disaster} struck {s.name}",
                        narrative=(
                            f"A {disaster} hit {s.name}, killing {pop_loss}% of "
                            f"the population and destroying {food_loss}% of the "
                            "food stores. The survivors are rebuilding, "
                            "stronger than before."
                        ),
                        severity=severity,
                        affected=[s.id],
                    )
                )

    # 9. Final collapse check (post-famine).
    for s in settlements.values():
        if s.active and s.population <= 0:
            _collapse(s, day, outcome)

    return outcome