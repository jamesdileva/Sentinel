"""Chat history schemas (Sprint v1.17 — persisted per-project chat rooms)."""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ChatMessageCreate(BaseModel):
    """One persisted exchange row. The frontend saves the question and the
    grounded answer exactly as produced by /rag/query (sources, model,
    confidence, error when the answer failed)."""

    # v1.17.18.4 (audit2 C4): was a free-form str — garbage roles could be
    # persisted and echoed back into the transcript.
    role: Literal["user", "assistant"]
    text: str
    sources: list[str] = []
    model: str | None = None
    confidence: float | None = None
    error: str | None = None


class ChatMessageRead(BaseModel):
    """Read shape mirrors ChatMessageCreate but tolerates rows persisted
    before `sources` was always a list (v1.17.18.4, audit2 D9): the column
    is nullable, so the read side must be too."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    role: str
    text: str
    sources: list[str] | None = None
    model: str | None = None
    confidence: float | None = None
    error: str | None = None
    created_at: datetime.datetime
