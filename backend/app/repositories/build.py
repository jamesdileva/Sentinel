"""Build log repository."""

from sqlmodel import select

from app.db.models import BuildLog
from app.repositories.base import Repository


class BuildLogRepository(Repository):
    model = BuildLog

    def get_by_project(self, project_id: str, limit: int = 50) -> list[BuildLog]:
        stmt = (
            select(BuildLog)
            .where(BuildLog.project_id == project_id)
            .order_by(BuildLog.started_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(stmt).all())
