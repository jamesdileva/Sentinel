"""Test result repository."""

from sqlmodel import select

from app.db.models import TestResult
from app.repositories.base import Repository


class TestRepository(Repository):
    model = TestResult

    def get_by_project(self, project_id: str, limit: int = 50) -> list[TestResult]:
        stmt = (
            select(TestResult)
            .where(TestResult.project_id == project_id)
            .order_by(TestResult.run_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(stmt).all())
