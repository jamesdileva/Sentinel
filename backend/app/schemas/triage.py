"""Error-triage schemas (later.md Tier 3, v1.17.12.0).

The evidence packet is deterministic (never AI-written); the summary is the
optional local-LLM description with provenance (model + created_at).
"""

import datetime

from pydantic import BaseModel, ConfigDict


class TriageSourceLine(BaseModel):
    line_number: int
    text: str


class TriageFrame(BaseModel):
    file: str
    relative_path: str
    line: int
    function: str | None = None
    source: list[TriageSourceLine] = []


class TriageEvidence(BaseModel):
    status: str
    actual_outcome: str | None = None
    error_lines: list[str] = []
    patterns: list[str] = []
    frames: list[TriageFrame] = []
    traceback_available: bool = False
    note: str | None = None


class TriageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    evidence: TriageEvidence
    summary: str | None = None
    model: str | None = None
    created_at: datetime.datetime
