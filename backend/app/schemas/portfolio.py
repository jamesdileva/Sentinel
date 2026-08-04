"""Portfolio intelligence response schemas."""

import datetime

from pydantic import BaseModel, ConfigDict


class PortfolioScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    build_status: str
    test_status: str
    documentation_pct: int
    security_status: str
    screenshots_available: bool
    portfolio_score: float
    updated_at: datetime.datetime


class PortfolioCandidate(BaseModel):
    """Ranked project with items missing for portfolio readiness."""

    project_id: str
    project_name: str
    score: float
    missing: list[str] = []


class FeatureMatrix(BaseModel):
    """Grid of all projects x features (build/test/docs/security/screenshots)."""

    projects: list[str] = []
    features: list[str] = ["build", "test", "docs", "security", "screenshots"]
    matrix: list[list[str]] = []
