"""TriageAnalysis repository (later.md Tier 3)."""

from sqlmodel import select

from app.db.models import TriageAnalysis
from app.repositories.base import Repository


class TriageAnalysisRepository(Repository):
    model = TriageAnalysis

    def by_session(self, session_id: str) -> list[TriageAnalysis]:
        stmt = (
            select(TriageAnalysis)
            .where(TriageAnalysis.session_id == session_id)
            .order_by(TriageAnalysis.created_at.desc())
        )
        return list(self.session.exec(stmt).all())
