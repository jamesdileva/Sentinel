"""Session recorder schemas (later.md Tier 1 + Tier 4)."""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    project_id: str
    title: str
    expected_output: str | None = None


class SessionCheckpointCreate(BaseModel):
    label: str


class SessionEndRequest(BaseModel):
    actual_outcome: str | None = None
    status: Literal["passed", "failed", "investigate"]


class SessionUpdate(BaseModel):
    title: str | None = None
    expected_output: str | None = None
    actual_outcome: str | None = None
    status: Literal["passed", "failed", "investigate"] | None = None


class SessionScreenshotCreate(BaseModel):
    checkpoint_id: str | None = None


class SessionCheckpointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    label: str
    at: datetime.datetime


class SessionScreenshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    checkpoint_id: str | None
    path: str
    captured_at: datetime.datetime


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    project_name: str | None = None
    title: str
    expected_output: str | None
    actual_outcome: str | None
    status: str
    started_at: datetime.datetime
    ended_at: datetime.datetime | None
    log_slice: str | None
    checkpoints: list[SessionCheckpointRead] = []
    screenshots: list[SessionScreenshotRead] = []


class SessionExportRead(BaseModel):
    copied: list[str]
    snippet: str
