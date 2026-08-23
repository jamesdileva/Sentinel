"""Startup sweep: orphaned BuildLog rows must not stay "running" forever.

Regression found live 2026-08-23 (Surfhop): a build queued behind knowledge
indexing was discarded by the process restart; its row kept
completed_at IS NULL, the derived status stayed "running", and the Builds
tab re-stuck on "Working…" on every page load.
"""

import datetime

from sqlmodel import Session

from app.db import connection
from app.db.models import BuildLog, Project
from app.repositories.build import ORPHAN_REASON, BuildLogRepository


def _seed(session: Session) -> Project:
    project = Project(name="sweep-test", path="/sweep-test", language="python")
    session.add(project)
    session.flush()
    session.add(
        BuildLog(project_id=project.id, completed_at=datetime.datetime(2026, 8, 1))
    )  # finished row — must be untouched
    session.add(BuildLog(project_id=project.id))  # orphaned row
    session.add(BuildLog(project_id=project.id))  # second orphaned row
    session.commit()
    return project


def test_mark_orphaned_as_failed(tmp_db):
    with Session(connection.get_engine()) as session:
        project = _seed(session)

        marked = BuildLogRepository(session).mark_orphaned_as_failed()
        assert marked == 2

        repo = BuildLogRepository(session)
        rows = repo.get_by_project(project.id)
        assert len(rows) == 3
        for log in rows:
            assert log.completed_at is not None
            if log.stderr == ORPHAN_REASON:
                assert log.exit_code == -1
                assert log.success is False
            else:
                # The genuinely-finished row keeps its original outcome.
                assert log.completed_at == datetime.datetime(2026, 8, 1)


def test_mark_orphaned_idempotent(tmp_db):
    with Session(connection.get_engine()) as session:
        _seed(session)
        repo = BuildLogRepository(session)
        assert repo.mark_orphaned_as_failed() == 2
        assert repo.mark_orphaned_as_failed() == 0
