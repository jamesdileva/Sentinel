"""Project response schemas."""

import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import ProjectStatus


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    path: str
    language: str
    framework: str | None = None
    stack: dict = Field(default_factory=dict)
    status: ProjectStatus
    health_score: float | None = None
    last_indexed: datetime.datetime | None = None
    last_scanned: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ProjectList(BaseModel):
    projects: list[ProjectRead]
    total: int


class ProjectFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    path: str
    language: str | None = None
    size_bytes: int | None = None
    summary: str | None = None
    created_at: datetime.datetime
