"""Git intelligence response schemas."""

import datetime

from pydantic import BaseModel, ConfigDict


class GitCommitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    hash: str
    message: str
    author: str | None = None
    timestamp: datetime.datetime | None = None
