"""WorldSimulatorService — orchestrates the deterministic world (docs/02 §11.5).

Persists state to the isolated world DB, advances days (manual or catch-up),
and exposes state/history/god-tool APIs. All decisions live in
`event_generator.simulate_day`; the service is persistence + timing only. An
optional narrator callable may enrich event text (AI flavor) but never changes
simulation state.
"""

import datetime
import random
from typing import Callable

from sqlmodel import Session, select

from app.core.config import settings
from app.core.logging import get_logger
from app.db.world_sim_models import (
    WorldEventRow,
    WorldRoad,
    WorldSettlement,
    WorldSimStateRow,
    get_world_engine,
)
from app.services.world_sim import names
from app.services.world_sim.event_generator import SimEvent, simulate_day
from app.services.world_sim.rules_engine import SettlementState, terrain_at
from app.services.world_sim.skill_system import (
    grant_survival_experience,
    skill_level,
)

logger = get_logger(__name__)

INITIAL_POPULATION = 120
INITIAL_FOOD_MULTIPLIER = 3
MIN_ABANDON_POPULATION = 5
DISASTER_SEVERITY = {"flood": 6, "drought": 6, "plague": 8}
DISASTER_TYPES = ("flood", "drought", "plague")

_SETTLEMENT_FIELDS = (
    "id",
    "name",
    "x",
    "y",
    "population",
    "food",
    "level",
    "experience",
    "status",
    "founded_day",
    "destroyed_day",
    "parent_id",
    "farmers",
    "builders",
    "merchants",
    "explorers",
    "construction",
)

Narrator = Callable[[SimEvent], None]


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class WorldSimulatorService:
    def __init__(
        self,
        engine=None,
        tick_seconds: int | None = None,
        max_catchup_days: int | None = None,
        seed: int | None = None,
        starting_settlements: int | None = None,
        time_scale: int | None = None,
        narrator: Narrator | None = None,
    ):
        self.engine = engine or get_world_engine()
        self.tick_seconds = tick_seconds or settings.world_sim_tick_seconds
        self.max_catchup_days = (
            max_catchup_days
            if max_catchup_days is not None
            else settings.world_sim_max_catchup_days
        )
        self.initial_seed = seed if seed is not None else settings.world_sim_seed
        self.starting_settlements = (
            starting_settlements
            if starting_settlements is not None
            else settings.world_sim_starting_settlements
        )
        self.base_time_scale = (
            time_scale if time_scale is not None else settings.world_sim_time_scale
        )
        self.narrator = narrator

    # ── bootstrap ───────────────────────────────────────────────────

    def ensure_world(self) -> None:
        """Create the single state row and initial settlements on first run."""
        with Session(self.engine) as session:
            state = session.get(WorldSimStateRow, "world")
            if state is None:
                state = WorldSimStateRow(
                    id="world",
                    day=0,
                    seed=self.initial_seed,
                    time_scale=self.base_time_scale,
                )
                session.add(state)
                session.commit()
            if session.exec(select(WorldSettlement)).first() is None:
                self._bootstrap(session, state.seed)
                session.commit()

    def _bootstrap(self, session: Session, seed: int) -> None:
        rng = random.Random(f"{seed}:init")
        occupied: set[tuple[int, int]] = set()
        for i in range(self.starting_settlements):
            site = self._find_site(rng, seed, occupied)
            occupied.add(site)
            session.add(
                WorldSettlement(
                    id=f"s{i}",
                    name=names.settlement_name(rng),
                    x=site[0],
                    y=site[1],
                    population=INITIAL_POPULATION,
                    food=INITIAL_POPULATION * INITIAL_FOOD_MULTIPLIER,
                    founded_day=0,
                    farmers=20,
                    builders=8,
                    merchants=3,
                    explorers=2,
                )
            )

    @staticmethod
    def _find_site(
        rng: random.Random, seed: int, occupied: set[tuple[int, int]]
    ) -> tuple[int, int]:
        for _ in range(500):
            x = 16 + rng.randint(-12, 12)
            y = 16 + rng.randint(-12, 12)
            if (x, y) not in occupied and terrain_at(x, y, seed) != "water":
                return (x, y)
        return (16, 16)

    # ── state mapping ───────────────────────────────────────────────

    def _sim_from_row(self, row: WorldSettlement) -> SettlementState:
        return SettlementState(
            id=row.id,
            name=row.name,
            x=row.x,
            y=row.y,
            population=row.population,
            food=row.food,
            level=row.level,
            experience=row.experience,
            status=row.status,
            founded_day=row.founded_day,
            destroyed_day=row.destroyed_day,
            parent_id=row.parent_id,
            farmers=row.farmers,
            builders=row.builders,
            merchants=row.merchants,
            explorers=row.explorers,
            construction=row.construction,
        )

    def _settlement_dict(self, sim: SettlementState, seed: int) -> dict:
        return {
            "id": sim.id,
            "name": sim.name,
            "x": sim.x,
            "y": sim.y,
            "population": sim.population,
            "food": sim.food,
            "level": sim.level,
            "experience": sim.experience,
            "skill_level": skill_level(sim.experience),
            "status": sim.status,
            "terrain": terrain_at(sim.x, sim.y, seed),
            "founded_day": sim.founded_day,
            "destroyed_day": sim.destroyed_day,
            "parent_id": sim.parent_id,
            "farmers": sim.farmers,
            "builders": sim.builders,
            "merchants": sim.merchants,
            "explorers": sim.explorers,
        }

    def _event_dict(self, row: WorldEventRow) -> dict:
        return {
            "id": row.id,
            "day": row.day,
            "event_type": row.event_type,
            "title": row.title,
            "narrative": row.narrative,
            "severity": row.severity,
            "affected_settlements": row.affected_settlements,
        }

    # ── simulation ──────────────────────────────────────────────────

    def advance_day(self, days: int = 1) -> int:
        """Advance the world by `days` world-days (1 = one day)."""
        self.ensure_world()
        with Session(self.engine) as session:
            world = session.get(WorldSimStateRow, "world")
            rows = {r.id: r for r in session.exec(select(WorldSettlement)).all()}
            roads = {
                (r.from_id, r.to_id) for r in session.exec(select(WorldRoad)).all()
            }
            sims = {rid: self._sim_from_row(r) for rid, r in rows.items()}
            seed = world.seed
            for _ in range(days):
                day = world.day + 1
                outcome = simulate_day(sims, list(roads), day, seed)
                for child in outcome.new_settlements:
                    sims[child.id] = child
                    rows[child.id] = WorldSettlement(
                        **{f: getattr(child, f) for f in _SETTLEMENT_FIELDS}
                    )
                    session.add(rows[child.id])
                for rid, sim in sims.items():
                    row = rows[rid]
                    for field_ in _SETTLEMENT_FIELDS[1:]:
                        setattr(row, field_, getattr(sim, field_))
                for a, b in outcome.new_roads:
                    if (a, b) not in roads:
                        roads.add((a, b))
                        session.add(WorldRoad(from_id=a, to_id=b, built_day=day))
                for event in outcome.events:
                    self._narrate(event)
                    session.add(
                        WorldEventRow(
                            day=day,
                            event_type=event.event_type,
                            title=event.title,
                            narrative=event.narrative,
                            severity=event.severity,
                            affected_settlements=event.affected,
                        )
                    )
                world.day = day
            world.updated_at = _utcnow()
            session.commit()
        return days

    def _narrate(self, event: SimEvent) -> None:
        if self.narrator is None:
            return
        try:
            self.narrator(event)
        except Exception:
            logger.debug("Narrator failed for event %s", event.title, exc_info=True)

    def catch_up(self) -> int:
        """Advance the world to reflect real elapsed time, bounded.

        Runs ~time_scale days per tick interval while the server is up, and
        catches up (bounded by max_catchup_days) after downtime.
        """
        self.ensure_world()
        with Session(self.engine) as session:
            world = session.get(WorldSimStateRow, "world")
            updated = world.updated_at
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=datetime.timezone.utc)
            elapsed_ticks = int((_utcnow() - updated).total_seconds()) // max(
                self.tick_seconds, 1
            )
            scale = max(world.time_scale, 1)
        if elapsed_ticks < 1:
            return 0
        days = min(elapsed_ticks * scale, self.max_catchup_days)
        return self.advance_day(days)

    # ── reads ───────────────────────────────────────────────────────

    def get_state(self, recent: int = 20) -> dict:
        self.ensure_world()
        with Session(self.engine) as session:
            world = session.get(WorldSimStateRow, "world")
            rows = session.exec(select(WorldSettlement)).all()
            road_rows = session.exec(select(WorldRoad)).all()
            events = session.exec(
                select(WorldEventRow).order_by(WorldEventRow.day.desc()).limit(recent)
            ).all()
            settlement_count = len(rows)
            event_count = len(session.exec(select(WorldEventRow.id)).all())
        settlements = [
            self._settlement_dict(self._sim_from_row(r), world.seed) for r in rows
        ]
        active = [s for s in settlements if s["status"] == "active"]
        return {
            "day_number": world.day,
            "time_scale": world.time_scale,
            "seed": world.seed,
            "updated_at": world.updated_at.isoformat(),
            "settlements": settlements,
            "roads": [
                {"from_id": r.from_id, "to_id": r.to_id, "built_day": r.built_day}
                for r in road_rows
            ],
            "recent_events": [self._event_dict(e) for e in events],
            "stats": {
                "settlements": settlement_count,
                "active": len(active),
                "abandoned": settlement_count - len(active),
                "population": sum(s["population"] for s in active),
                "roads": len(road_rows),
                "events": event_count,
            },
        }

    def get_history(self, limit: int = 100, before: int | None = None) -> list[dict]:
        self.ensure_world()
        with Session(self.engine) as session:
            query = select(WorldEventRow).order_by(
                WorldEventRow.day.desc(), WorldEventRow.created_at.desc()
            )
            if before is not None:
                query = query.where(WorldEventRow.day < before)
            rows = session.exec(query.limit(limit)).all()
        return [self._event_dict(e) for e in rows][::-1]

    def get_settlement(self, settlement_id: str) -> dict | None:
        self.ensure_world()
        with Session(self.engine) as session:
            world = session.get(WorldSimStateRow, "world")
            row = session.get(WorldSettlement, settlement_id)
            if row is None:
                return None
            roads = session.exec(
                select(WorldRoad).where(
                    (WorldRoad.from_id == settlement_id)
                    | (WorldRoad.to_id == settlement_id)
                )
            ).all()
        detail = self._settlement_dict(self._sim_from_row(row), world.seed)
        detail["roads"] = [
            {"from_id": r.from_id, "to_id": r.to_id, "built_day": r.built_day}
            for r in roads
        ]
        return detail

    # ── god tools ───────────────────────────────────────────────────

    def reset(self, seed: int | None = None) -> None:
        """Wipe the world and start again at day 0 with a (new) seed."""
        with Session(self.engine) as session:
            world = session.get(WorldSimStateRow, "world")
            for table in (WorldSettlement, WorldRoad, WorldEventRow):
                for row in session.exec(select(table)).all():
                    session.delete(row)
            world.day = 0
            world.seed = seed if seed is not None else self.initial_seed
            world.time_scale = self.base_time_scale
            world.updated_at = _utcnow()
            session.commit()
        self.ensure_world()

    def set_time_scale(self, scale: int) -> None:
        """Accelerate/decelerate: each tick interval advances `scale` days."""
        scale = max(1, min(scale, 10))
        with Session(self.engine) as session:
            world = session.get(WorldSimStateRow, "world")
            world.time_scale = scale
            session.commit()

    def trigger_disaster(self, settlement_id: str, disaster_type: str) -> bool:
        """God tool: force a disaster on a settlement. Returns False if the
        settlement is unknown or already abandoned."""
        if disaster_type not in DISASTER_TYPES:
            raise ValueError(f"Unknown disaster type: {disaster_type}")
        self.ensure_world()
        with Session(self.engine) as session:
            world = session.get(WorldSimStateRow, "world")
            row = session.get(WorldSettlement, settlement_id)
            if row is None or row.status != "active":
                return False
            severity = DISASTER_SEVERITY[disaster_type]
            row.population = max(0, row.population - row.population * 20 // 100)
            row.food = max(0, row.food - row.food * 30 // 100)
            if row.population < MIN_ABANDON_POPULATION:
                row.population = 0
                row.status = "abandoned"
                row.destroyed_day = world.day + 1
                title = f"{row.name} has collapsed"
                narrative = (
                    f"The {disaster_type} overwhelmed {row.name}; "
                    "the settlement was abandoned."
                )
            else:
                row.experience += grant_survival_experience(severity)
                title = f"A {disaster_type} struck {row.name}"
                narrative = (
                    f"The {disaster_type} hit {row.name}, killing 20% of its "
                    "people and destroying 30% of its food stores. The "
                    "survivors are rebuilding, stronger than before."
                )
            session.add(
                WorldEventRow(
                    day=world.day + 1,
                    event_type="natural",
                    title=title,
                    narrative=narrative,
                    severity=severity,
                    affected_settlements=[row.id],
                )
            )
            session.commit()
        return True
