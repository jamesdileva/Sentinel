"""World Simulator schemas (Sprint 9, docs/02 §11.6).

Response schemas mirror the dict shapes produced by
`WorldSimulatorService`; request schemas cover the god-tool endpoints.
"""

from pydantic import BaseModel, Field


class WorldRoadRead(BaseModel):
    from_id: str
    to_id: str
    built_day: int


class WorldSettlementRead(BaseModel):
    id: str
    name: str
    x: int
    y: int
    population: int
    food: int
    level: int
    experience: int
    skill_level: int
    status: str  # "active" | "abandoned"
    terrain: str
    founded_day: int
    destroyed_day: int | None = None
    parent_id: str | None = None
    farmers: int
    builders: int
    merchants: int
    explorers: int


class WorldSettlementDetailRead(WorldSettlementRead):
    roads: list[WorldRoadRead] = []


class WorldEventRead(BaseModel):
    id: str
    day: int
    event_type: str  # discovery | trade | conflict | natural | social
    title: str
    narrative: str
    severity: int = 1  # 1-10
    affected_settlements: list[str] = []


class WorldStatsRead(BaseModel):
    settlements: int
    active: int
    abandoned: int
    population: int
    roads: int
    events: int


class WorldSimStateRead(BaseModel):
    day_number: int
    time_scale: int
    seed: int
    updated_at: str
    settlements: list[WorldSettlementRead]
    roads: list[WorldRoadRead]
    recent_events: list[WorldEventRead]
    stats: WorldStatsRead


class WorldTickRequest(BaseModel):
    days: int = Field(1, ge=1, le=365)


class WorldTickResponse(BaseModel):
    days_advanced: int
    day_number: int


class WorldResetRequest(BaseModel):
    seed: int | None = None


class WorldAccelerateRequest(BaseModel):
    time_scale: int = Field(1, ge=1, le=10)


class WorldDisasterRequest(BaseModel):
    settlement_id: str
    disaster_type: str


class WorldDisasterResponse(BaseModel):
    settlement_id: str
    disaster_type: str
    applied: bool
