"""Security finding repository."""

from sqlmodel import delete, select

from app.db.models import SecurityFinding
from app.repositories.base import Repository


class SecurityRepository(Repository):
    model = SecurityFinding

    def get_by_project(
        self, project_id: str, limit: int | None = 500
    ) -> list[SecurityFinding]:
        stmt = (
            select(SecurityFinding)
            .where(SecurityFinding.project_id == project_id)
            .order_by(SecurityFinding.detected_at.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.exec(stmt).all())

    def get_open(
        self, project_id: str, limit: int | None = 500
    ) -> list[SecurityFinding]:
        stmt = (
            select(SecurityFinding)
            .where(SecurityFinding.project_id == project_id)
            .where(SecurityFinding.resolved == False)  # noqa: E712
            .order_by(SecurityFinding.detected_at.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.exec(stmt).all())

    def delete_resolved(self, project_id: str) -> int:
        """Delete resolved findings for a project (v1.17.7.7). Open findings
        are never touched — resolution keeps them for the next scan's
        idempotence keys. Returns the number of rows deleted.

        v1.17.18.4 (audit2 D7): one bulk DELETE statement, and no commit in
        here — transaction ownership belongs to the caller (every other
        repository only flushes); the old row-loop + mid-method commit could
        leave partial deletes committed with no rollback on failure."""
        result = self.session.exec(
            delete(SecurityFinding)
            .where(SecurityFinding.project_id == project_id)
            .where(SecurityFinding.resolved == True)  # noqa: E712
        )
        self.session.flush()
        return int(result.rowcount or 0)
