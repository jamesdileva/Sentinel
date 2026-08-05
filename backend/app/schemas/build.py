"""Build log response schemas."""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

JobStatusValue = Literal["queued", "running", "succeeded", "failed"]


class BuildTrigger(BaseModel):
    project_id: str


class BuildLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    exit_code: int | None = None
    success: bool | None = None
    stdout: str | None = None
    stderr: str | None = None
    commands: dict | None = None


class JobStatus(BaseModel):
    """Async job state used by build status polling."""

    id: str
    project_id: str
    status: JobStatusValue
    success: bool | None = None
    exit_code: int | None = None
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None


def build_status_from_log(log) -> JobStatus:
    """Derive a JobStatus from a BuildLog row (model_config from_attributes)."""
    if log.completed_at is not None:
        status: JobStatusValue = "succeeded" if log.success else "failed"
    else:
        status = "running"
    return JobStatus(
        id=log.id,
        project_id=log.project_id,
        status=status,
        success=log.success,
        exit_code=log.exit_code,
        started_at=log.started_at,
        completed_at=log.completed_at,
    )
