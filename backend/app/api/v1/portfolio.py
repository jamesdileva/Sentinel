"""Portfolio endpoints — /api/v1/portfolio.

Sprint 10. Health scores are recomputed deterministically on read from stored
build/test/security/file rows (no AI, no extra jobs). Reading also refreshes the
`PortfolioScore` table so the CLI and observability see the same numbers.

v1.17.19.21 (audit B3): `POST /scores/refresh` is the explicit invalidation the
audit's recommended architecture asks for. Reads stay lazy; this forces the
recompute when the user wants it now rather than when evidence next changes.
"""

from fastapi import APIRouter, Depends
from fastapi import Query as QueryParam
from sqlmodel import Session

from app.core.exceptions import NotFoundError
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
    """Health scores for every indexed project (recomputed when evidence moved,
    otherwise served from the cached row)."""
    return service.scores()


@router.post("/scores/refresh", response_model=list[PortfolioScoreRead])
def portfolio_scores_refresh(
    project_id: str | None = QueryParam(None, description="Recompute just one"),
    service: PortfolioService = Depends(get_portfolio_service),
) -> list[PortfolioScoreRead]:
    """Force a recompute of the cached score rows (audit B3).

    Deterministic and synchronous — a handful of indexed queries per project,
    no job pool and no AI. This is the leg of the audit's architecture that
    reading alone cannot give: a row cached under an *older component
    definition* has evidence timestamps that never move, so only a forced
    recompute (or the startup sweep) heals it.
    """
    try:
        rows = service.refresh(project_id)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc
    return [PortfolioScoreRead.model_validate(row) for row in rows]


@router.get("/best-candidates", response_model=list[PortfolioCandidate])
def best_candidates(
    min_score: float = QueryParam(70.0, ge=0.0, le=100.0),
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
