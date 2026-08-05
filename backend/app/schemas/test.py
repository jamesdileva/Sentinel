"""Test result response schemas."""

import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.job import JobEnvelope


class TestResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    run_at: datetime.datetime
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_seconds: float | None = None
    framework: str | None = None
    summary: str | None = None


class TestRunResponse(JobEnvelope):
    pass
