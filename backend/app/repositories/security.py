"""Security finding repository."""

from sqlmodel import select

from app.db.models import SecurityFinding
from app.repositories.base import Repository


class SecurityRepository(Repository):
    model = SecurityFinding

    def get_by_project(self, project_id: str) -> list[SecurityFinding]:
        stmt = (
            select(SecurityFinding)
            .where(SecurityFinding.project_id == project_id)
            .order_by(SecurityFinding.detected_at.desc())
        )
        return list(self.session.exec(stmt).all())

    def get_open(self, project_id: str) -> list[SecurityFinding]:
        stmt = (
            select(SecurityFinding)
            .where(SecurityFinding.project_id == project_id)
            .where(SecurityFinding.resolved == False)  # noqa: E712
            .order_by(SecurityFinding.detected_at.desc())
        )
        return list(self.session.exec(stmt).all())

    def delete_resolved(self, project_id: str) -> int:
        """Delete resolved findings for a project (v1.17.7.7). Open findings
        are never touched — resolution keeps them for the next scan's
        idempotence keys. Returns the number of rows deleted."""
        stmt = (
            select(SecurityFinding)
            .where(SecurityFinding.project_id == project_id)
            .where(SecurityFinding.resolved == True)  # noqa: E712
        )
        rows = list(self.session.exec(stmt).all())
        for row in rows:
            self.session.delete(row)
        self.session.commit()
        return len(rows)
