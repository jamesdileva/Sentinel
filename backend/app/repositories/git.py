"""Git commit repository."""

from sqlmodel import select

from app.db.models import GitCommit
from app.repositories.base import Repository


class GitCommitRepository(Repository):
    model = GitCommit

    def get_by_project(self, project_id: str, limit: int = 100) -> list[GitCommit]:
        stmt = (
            select(GitCommit)
            .where(GitCommit.project_id == project_id)
            .order_by(GitCommit.timestamp.desc())
            .limit(limit)
        )
        return list(self.session.exec(stmt).all())

    def hashes_for_project(self, project_id: str) -> set[str]:
        stmt = select(GitCommit.hash).where(GitCommit.project_id == project_id)
        return {row for row in self.session.exec(stmt).all()}
