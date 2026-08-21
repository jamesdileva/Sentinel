"""Dependency repository."""

from sqlmodel import delete, select

from app.db.models import Dependency
from app.repositories.base import Repository


class DependencyRepository(Repository):
    model = Dependency

    def get_by_project(
        self, project_id: str, limit: int | None = None
    ) -> list[Dependency]:
        stmt = select(Dependency).where(Dependency.project_id == project_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.exec(stmt).all())

    def delete_by_project(self, project_id: str) -> None:
        self.session.exec(delete(Dependency).where(Dependency.project_id == project_id))
        self.session.flush()
