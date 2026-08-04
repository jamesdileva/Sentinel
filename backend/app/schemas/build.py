"""Build log response schemas."""

import datetime

from pydantic import BaseModel, ConfigDict


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
