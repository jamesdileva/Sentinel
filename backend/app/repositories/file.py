"""Project file repository."""

from sqlmodel import delete, select

from app.db.models import ProjectFile
from app.repositories.base import Repository


class ProjectFileRepository(Repository):
    model = ProjectFile

    def get_by_project(self, project_id: str) -> list[ProjectFile]:
        stmt = select(ProjectFile).where(ProjectFile.project_id == project_id)
        return list(self.session.exec(stmt).all())

    def get_by_path(self, project_id: str, path: str) -> ProjectFile | None:
        stmt = (
            select(ProjectFile)
            .where(ProjectFile.project_id == project_id)
            .where(ProjectFile.path == path)
        )
        return self.session.exec(stmt).first()

    def delete_by_project(self, project_id: str) -> None:
        self.session.exec(
            delete(ProjectFile).where(ProjectFile.project_id == project_id)
        )
        self.session.flush()
