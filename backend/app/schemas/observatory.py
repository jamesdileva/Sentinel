"""Observatory response schemas.

Galaxy graph, activity timeline, and recursive architecture tree (docs/02 §14.6).
"""

import datetime

from pydantic import BaseModel, Field


class GalaxyNode(BaseModel):
    id: str
    kind: str  # "project" | "tech"
    label: str
    detail: str | None = None


class GalaxyLink(BaseModel):
    source: str  # node id
    target: str  # node id
    tech: str


class GalaxyGraph(BaseModel):
    nodes: list[GalaxyNode] = Field(default_factory=list)
    links: list[GalaxyLink] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    at: datetime.datetime
    kind: str  # project-created | commit | build | test | finding
    project_id: str
    project_name: str
    message: str


class Timeline(BaseModel):
    events: list[TimelineEvent] = Field(default_factory=list)
    has_more: bool = False


class ArchitectureNode(BaseModel):
    """A folder or file in the project's component tree."""

    name: str
    path: str
    kind: str  # "dir" | "file"
    count: int = 0  # total files beneath a dir (files in a subtree) or 0
    children: list["ArchitectureNode"] = Field(default_factory=list)


ArchitectureNode.model_rebuild()
