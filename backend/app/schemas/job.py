"""Shared async-job schemas (Sprint 7)."""

from typing import Literal

from pydantic import BaseModel


class JobEnvelope(BaseModel):
    """Response body for enqueue endpoints: a Celery task id plus its status."""

    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
