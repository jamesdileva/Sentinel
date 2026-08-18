"""Tester schemas (later.md Tier 2)."""

from typing import Literal

from pydantic import BaseModel


class FeatureDescriptor(BaseModel):
    """A project's UI click-through feature (docs/clickthrough_plan.md)."""

    name: str
    description: str | None = None


class TesterDescriptor(BaseModel):
    """What a project's tester is �?" used to enable the Run tester button."""

    name: str
    description: str | None = None
    kind: Literal["custom", "default-smoke"]
    features: list[FeatureDescriptor] = []


class TesterRunRequest(BaseModel):
    project_id: str
