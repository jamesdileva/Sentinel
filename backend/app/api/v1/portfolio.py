"""Portfolio endpoints — /api/v1/portfolio.

Sprint 10. Health scores are recomputed deterministically on read from stored
build/test/security/file rows (no AI, no extra jobs). Reading also refreshes the
`PortfolioScore` table so the CLI and observability see the same numbers.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db.connection import get_session
from app.schemas import (
    FeatureMatrix,
    PortfolioCandidate,
    PortfolioScoreRead,
    PortfolioSummary,
)
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def get_portfolio_service(session: Session = Depends(get_session)) -> PortfolioService:
    """FastAPI dependency so tests can override the service with a temp DB."""
    return PortfolioService(session)


@router.get("/scores", response_model=list[PortfolioScoreRead])
def portfolio_scores(
    service: PortfolioService = Depends(get_portfolio_service),
) -> list[PortfolioScoreRead]:
    """Health scores for every indexed project (freshly recomputed)."""
    return service.scores()


@router.get("/best-candidates", response_model=list[PortfolioCandidate])
def best_candidates(
    min_score: float = 70.0,
    service: PortfolioService = Depends(get_portfolio_service),
) -> list[PortfolioCandidate]:
    """Job-ready projects ranked by score with their missing items."""
    return service.get_best_candidates(min_score=min_score)


@router.get("/feature-matrix", response_model=FeatureMatrix)
def feature_matrix(
    service: PortfolioService = Depends(get_portfolio_service),
) -> FeatureMatrix:
    """Grid of every project x feature (build/test/docs/security/screenshots)."""
    return service.feature_matrix()


@router.get("/summary", response_model=PortfolioSummary)
def portfolio_summary(
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioSummary:
    """Dashboard stats: project count, buildable projects, open findings,
    average health. Read-only; cached like the score table (Sprint 15)."""
    return PortfolioSummary(**service.summary())
