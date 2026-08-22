"""AppSession repository (later.md Tier 1)."""

from sqlmodel import col, select

from app.db.models import AppSession, SessionCheckpoint, SessionScreenshot
from app.repositories.base import Repository


class SessionRepository(Repository):
    model = AppSession

    def list_sessions(
        self,
        project_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[AppSession]:
        stmt = select(AppSession).order_by(AppSession.started_at.desc())
        if project_id:
            stmt = stmt.where(AppSession.project_id == project_id)
        if status:
            stmt = stmt.where(AppSession.status == status)
        return list(self.session.exec(stmt.limit(limit)).all())


class SessionCheckpointRepository(Repository):
    model = SessionCheckpoint

    def by_session(self, session_id: str) -> list[SessionCheckpoint]:
        stmt = (
            select(SessionCheckpoint)
            .where(SessionCheckpoint.session_id == session_id)
            .order_by(SessionCheckpoint.at.asc())
        )
        return list(self.session.exec(stmt).all())

    def by_sessions(self, session_ids: list[str]) -> list[SessionCheckpoint]:
        """One IN query for many sessions (v1.17.18.6, audit2 C6), each
        session's checkpoints ordered oldest-first."""
        if not session_ids:
            return []
        stmt = (
            select(SessionCheckpoint)
            .where(col(SessionCheckpoint.session_id).in_(session_ids))
            .order_by(SessionCheckpoint.at.asc())
        )
        return list(self.session.exec(stmt).all())


class SessionScreenshotRepository(Repository):
    model = SessionScreenshot

    def by_session(self, session_id: str) -> list[SessionScreenshot]:
        stmt = select(SessionScreenshot).where(
            SessionScreenshot.session_id == session_id
        )
        return list(
            self.session.exec(stmt.order_by(SessionScreenshot.captured_at)).all()
        )

    def by_sessions(self, session_ids: list[str]) -> list[SessionScreenshot]:
        """One IN query for many sessions (v1.17.18.6, audit2 C6)."""
        if not session_ids:
            return []
        stmt = (
            select(SessionScreenshot)
            .where(col(SessionScreenshot.session_id).in_(session_ids))
            .order_by(SessionScreenshot.captured_at)
        )
        return list(self.session.exec(stmt).all())

    def older_than(self, days: int) -> list[SessionScreenshot]:
        """All screenshots captured before (now - days), oldest first."""
        import datetime

        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=days
        )
        stmt = select(SessionScreenshot).where(SessionScreenshot.captured_at < cutoff)
        return list(
            self.session.exec(stmt.order_by(SessionScreenshot.captured_at)).all()
        )
