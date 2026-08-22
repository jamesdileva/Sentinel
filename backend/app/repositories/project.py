"""Project repository."""

from collections.abc import Iterable

from sqlmodel import col, select

from app.db.models import Project
from app.repositories.base import Repository


class ProjectRepository(Repository):
    model = Project

    def get_by_path(self, path: str) -> Project | None:
        stmt = select(Project).where(Project.path == path)
        return self.session.exec(stmt).first()

    def by_ids(self, ids: Iterable[str]) -> dict[str, Project]:
        """One IN query -> {id: project} (v1.17.18.6, audit2 C6)."""
        ids = list(ids)
        if not ids:
            return {}
        stmt = select(Project).where(col(Project.id).in_(ids))
        return {p.id: p for p in self.session.exec(stmt).all()}
