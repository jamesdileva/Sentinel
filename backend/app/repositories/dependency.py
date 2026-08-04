"""Dependency repository."""

from sqlmodel import delete, select

from app.db.models import Dependency
from app.repositories.base import Repository


class DependencyRepository(Repository):
    model = Dependency

    def get_by_project(self, project_id: str) -> list[Dependency]:
        stmt = select(Dependency).where(Dependency.project_id == project_id)
        return list(self.session.exec(stmt).all())

    def get_by_name(self, project_id: str, name: str) -> Dependency | None:
        stmt = (
            select(Dependency)
            .where(Dependency.project_id == project_id)
            .where(Dependency.name == name)
        )
        return self.session.exec(stmt).first()

    def delete_by_project(self, project_id: str) -> None:
        self.session.exec(delete(Dependency).where(Dependency.project_id == project_id))
        self.session.flush()
