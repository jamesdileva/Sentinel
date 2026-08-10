"""Chat history schemas (Sprint v1.17 — persisted per-project chat rooms)."""

import datetime

from pydantic import BaseModel, ConfigDict


class ChatMessageCreate(BaseModel):
    """One persisted exchange row. The frontend saves the question and the
    grounded answer exactly as produced by /rag/query (sources, model,
    confidence, error when the answer failed)."""

    role: str
    text: str
    sources: list[str] = []
    model: str | None = None
    confidence: float | None = None
    error: str | None = None


class ChatMessageRead(ChatMessageCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    created_at: datetime.datetime
