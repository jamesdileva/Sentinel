"""Build log response schemas."""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

JobStatusValue = Literal["queued", "running", "succeeded", "failed", "skipped"]


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
    # v1.17.8.0 build->open: the startup command launched after the build
    # (or instead of one), None when nothing was launched.
    launch_command: str | None = None


class JobStatus(BaseModel):
    """Async job state used by build status polling."""

    id: str
    project_id: str
    status: JobStatusValue
    success: bool | None = None
    exit_code: int | None = None
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    # v1.17.8.0: the startup command launched when the job finished.
    launch_command: str | None = None


def build_status_from_log(log) -> JobStatus:
    """Derive a JobStatus from a BuildLog row (model_config from_attributes).

    v1.17.7.5: a completed build with `success=None` means no command was
    discovered — "skipped", not "failed" (and never the old false "passed").
    """
    if log.completed_at is not None:
        if log.success is True:
            status: JobStatusValue = "succeeded"
        elif log.success is False:
            status = "failed"
        else:
            status = "skipped"
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
        launch_command=log.launch_command,
    )
