"""World Simulator response schemas (optional module, Sprint 9)."""

import datetime

from pydantic import BaseModel, ConfigDict


class WorldEvent(BaseModel):
    event_type: str  # "discovery", "trade", "conflict", "natural", "social"
    description: str
    severity: int = 1  # 1-10
    affected_entities: list[str] = []


class WorldSimDay(BaseModel):
    day: int
    events: list[WorldEvent] = []


class WorldSimStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day_number: int
    events: dict = {}
    nations: dict = {}
    economy: dict = {}
    updated_at: datetime.datetime
