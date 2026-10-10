"""Shared async-job schemas (Sprint 7)."""

import datetime
from typing import Literal

from pydantic import BaseModel


class JobEnvelope(BaseModel):
    """Response body for enqueue endpoints: a Celery task id plus its status."""

    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]


class JobRead(BaseModel):
    """One persisted generic job row (v1.17.19.11, audit B5): the single
    pollable lifecycle shared by builds, tests, testers, scans and knowledge
    jobs, whatever domain record each one also writes."""

    id: str
    type: str
    project_id: str | None
    status: str
    created_at: datetime.datetime
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    error: str | None
    result_ref: str | None
