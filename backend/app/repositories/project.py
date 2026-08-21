"""Project repository."""

from sqlmodel import select

from app.db.models import Project
from app.repositories.base import Repository


class ProjectRepository(Repository):
    model = Project

    def get_by_path(self, path: str) -> Project | None:
        stmt = select(Project).where(Project.path == path)
        return self.session.exec(stmt).first()
