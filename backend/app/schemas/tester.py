"""Tester schemas (later.md Tier 2)."""

from typing import Literal

from pydantic import BaseModel


class TesterDescriptor(BaseModel):
    """What a project's tester is — used to enable the Run tester button."""

    name: str
    description: str | None = None
    kind: Literal["custom", "default-smoke"]


class TesterRunRequest(BaseModel):
    project_id: str
