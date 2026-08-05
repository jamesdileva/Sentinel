"""Knowledge summary repository."""

from sqlmodel import select

from app.db.models import KnowledgeSummary
from app.repositories.base import Repository


class KnowledgeSummaryRepository(Repository):
    model = KnowledgeSummary

    def get_by_project(
        self, project_id: str, summary_type: str | None = None
    ) -> list[KnowledgeSummary]:
        stmt = select(KnowledgeSummary).where(KnowledgeSummary.project_id == project_id)
        if summary_type is not None:
            stmt = stmt.where(KnowledgeSummary.type == summary_type)
        stmt = stmt.order_by(KnowledgeSummary.generated_at.desc())
        return list(self.session.exec(stmt).all())
