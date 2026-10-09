"""RAG schemas — semantic search and Q&A (docs/02 §2.3)."""

import datetime

from pydantic import BaseModel, Field


class RagResult(BaseModel):
    """A single retrieved context chunk with provenance."""

    content: str
    source: str  # chroma collection name
    project_id: str
    file_path: str | None = None
    distance: float


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    project_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class RagSearchResponse(BaseModel):
    query: str
    results: list[RagResult]


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    project_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class RagResponse(BaseModel):
    """Grounded answer with sources and AI provenance (docs/01 §16.2).

    `confidence` is a deterministic retrieval score (1 - best cosine
    distance), NOT a calibrated probability of the answer being correct —
    audit A8, v1.17.19.8. When it is 0.0 the answer is one of Sentinel's
    deterministic refusals: no indexed evidence at all, or the nearest
    content was further away than `settings.rag_relevance_floor`.
    """

    answer: str
    sources: list[RagResult]
    model: str
    generated_at: datetime.datetime
    confidence: float


class RagIndexRequest(BaseModel):
    project_id: str
    with_summary: bool = False
