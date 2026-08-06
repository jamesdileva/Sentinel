"""World Simulator database — fully isolated from project data (docs/02 §11).

Uses its own SQLite file and its own SQLAlchemy metadata so the main
`init_db()` never touches world tables. Tables are created on first use via
`get_world_engine()`.
"""

import datetime
import uuid

from sqlalchemy import JSON, Column, MetaData
from sqlalchemy import create_engine
from sqlmodel import Field, SQLModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

world_sim_metadata = MetaData()


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class WorldSimStateRow(SQLModel, table=True):
    __tablename__ = "world_sim_state"
    metadata = world_sim_metadata

    id: str = Field(default="world", primary_key=True)
    day: int = 0
    seed: int = 42
    time_scale: int = 1
    updated_at: datetime.datetime = Field(default_factory=_utcnow)


class WorldSettlement(SQLModel, table=True):
    __tablename__ = "world_settlements"
    metadata = world_sim_metadata

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    x: int
    y: int
    population: int
    food: int
    level: int = 1
    experience: int = 0
    status: str = "active"  # "active" | "abandoned"
    founded_day: int
    destroyed_day: int | None = None
    parent_id: str | None = None
    farmers: int = 10
    builders: int = 5
    merchants: int = 2
    explorers: int = 1
    construction: int = 0


class WorldRoad(SQLModel, table=True):
    __tablename__ = "world_roads"
    metadata = world_sim_metadata

    id: str = Field(default_factory=_uuid, primary_key=True)
    from_id: str
    to_id: str
    built_day: int


class WorldEventRow(SQLModel, table=True):
    __tablename__ = "world_events"
    metadata = world_sim_metadata

    id: str = Field(default_factory=_uuid, primary_key=True)
    day: int
    event_type: str  # discovery | trade | conflict | natural | social
    title: str
    narrative: str
    severity: int = 1  # 1-10
    affected_settlements: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime.datetime = Field(default_factory=_utcnow)


_engine = None


def get_world_engine():
    """Create the world DB engine, creating tables on first access."""
    global _engine
    if _engine is None:
        settings.world_sim_db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{settings.world_sim_db_path}",
            connect_args={"check_same_thread": False},
        )
        world_sim_metadata.create_all(_engine)
        logger.info("World DB initialized: %s", settings.world_sim_db_path)
    return _engine