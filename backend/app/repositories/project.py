"""Project repository."""

from sqlmodel import select

from app.db.models import Project
from app.repositories.base import Repository


class ProjectRepository(Repository):
    model = Project

    def get_by_path(self, path: str) -> Project | None:
        stmt = select(Project).where(Project.path == path)
        return self.session.exec(stmt).first()

    def get_by_name(self, name: str) -> Project | None:
        stmt = select(Project).where(Project.name == name)
        return self.session.exec(stmt).first()

    def list_by_status(self, status: str) -> list[Project]:
        stmt = select(Project).where(Project.status == status)
        return list(self.session.exec(stmt).all())
