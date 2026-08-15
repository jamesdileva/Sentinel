"""AppSession repository (later.md Tier 1)."""

from sqlmodel import select

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


class SessionScreenshotRepository(Repository):
    model = SessionScreenshot

    def by_session(self, session_id: str) -> list[SessionScreenshot]:
        stmt = select(SessionScreenshot).where(
            SessionScreenshot.session_id == session_id
        )
        return list(
            self.session.exec(stmt.order_by(SessionScreenshot.captured_at)).all()
        )
