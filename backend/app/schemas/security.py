"""Security finding schemas.

`SecurityFindingCreate` mirrors docs/02_Implementation_Guide.md §9.2.
"""

import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import Severity
from app.schemas.job import JobEnvelope


class SecurityFindingCreate(BaseModel):
    type: str  # "vulnerability", "secret", "static_analysis"
    severity: Severity
    title: str
    description: str | None = None
    file_path: str | None = None
    line_number: int | None = None
    cve_id: str | None = None
    remediation: str | None = None


class SecurityFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    type: str
    severity: Severity
    title: str
    description: str | None = None
    ai_explanation: str | None = None
    file_path: str | None = None
    line_number: int | None = None
    cve_id: str | None = None
    remediation: str | None = None
    resolved: bool
    detected_at: datetime.datetime


class ScanResponse(JobEnvelope):
    pass


class SecurityClearRead(BaseModel):
    """Response for DELETE /security/findings (v1.17.18.5, audit2 C5)."""

    deleted: int
