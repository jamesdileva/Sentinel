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
    added_files: list[str] | None = None
    modified_files: list[str] | None = None
    deleted_files: list[str] | None = None
    feature_tags: list[str] | None = None


class FeatureTimelineItem(BaseModel):
    """A single point on the project feature timeline."""

    date: datetime.datetime | None = None
    feature: str
    commit_hash: str
    sprint: int | None = None
