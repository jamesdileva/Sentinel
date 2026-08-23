"""Build log repository."""

import datetime

from sqlmodel import select

from app.db.models import BuildLog
from app.repositories.base import Repository

ORPHAN_REASON = "Aborted: Sentinel restarted before the job finished."


class BuildLogRepository(Repository):
    model = BuildLog

    def mark_orphaned_as_failed(
        self,
        reason: str = ORPHAN_REASON,
        completed_at: datetime.datetime | None = None,
    ) -> int:
        """Close out rows abandoned mid-run (`completed_at IS NULL`).

        The scheduler discards queued/running futures on shutdown without any
        DB cleanup, leaving eternal-"running" rows whose derived status keeps
        the Builds tab stuck on "Working…" across restarts. Called during
        startup so every restart self-heals (Rule 3). Returns rows updated.
        """
        orphans = list(
            self.session.exec(
                select(BuildLog).where(BuildLog.completed_at.is_(None))
            ).all()
        )
        finished = completed_at or datetime.datetime.now(datetime.timezone.utc)
        for log in orphans:
            log.completed_at = finished
            log.exit_code = -1
            log.success = False
            log.stderr = reason
        if orphans:
            self.session.commit()
        return len(orphans)

    def get_by_project(self, project_id: str, limit: int = 50) -> list[BuildLog]:
        stmt = (
            select(BuildLog)
            .where(BuildLog.project_id == project_id)
            .order_by(BuildLog.started_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(stmt).all())
