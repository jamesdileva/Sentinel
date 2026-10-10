"""Audit Batch 2 close-out: unified stale-running recovery (v1.17.19.14).

Every job type that can claim work is "in flight" — BuildLog, the generic
Job ledger, and AppSession — must self-heal after an interrupt that skips
B7's graceful drain. Each already had (or lacked) its own sweep; this
covers one policy, one call site.
"""

from sqlmodel import Session

from app.db import connection
from app.db.models import AppSession, Job, JobState, Project, SessionStatus
from app.repositories.build import BuildLogRepository
from app.repositories.job import JobRepository
from app.repositories.session import SessionRepository
from app.services.stale_recovery import (
    RESTART_REASON,
    RecoveryReport,
    recover_interrupted_work,
)


def _project_id(name: str) -> str:
    """BuildLog and AppSession both require a real project (NOT NULL + FK)."""
    with Session(connection.get_engine()) as session:
        row = Project(name=name, path=f"/tmp/{name}", language="python")
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def _seed_session(status: SessionStatus, title: str = "Tester: X") -> str:
    pid = _project_id(f"sess-{title[:12]}")
    with Session(connection.get_engine()) as session:
        row = AppSession(project_id=pid, title=title, status=status)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def _seed_job(status: JobState, job_id: str) -> str:
    with Session(connection.get_engine()) as session:
        repo = JobRepository(session)
        repo.create(job_id, "test", None)
        if status is JobState.RUNNING:
            repo.mark_running(job_id)
        elif status is JobState.SUCCEEDED:
            repo.mark_succeeded(job_id)
        return job_id


def _seed_build(job_id: str, completed: bool) -> str:
    import datetime

    from app.db.models import BuildLog

    pid = _project_id(f"build-{job_id}")
    now = datetime.datetime.now(datetime.timezone.utc)
    with Session(connection.get_engine()) as session:
        session.add(
            BuildLog(
                id=job_id,
                project_id=pid,
                started_at=now,
                completed_at=now if completed else None,
                success=True,
            )
        )
        session.commit()
        return job_id


def _session_row(session_id: str) -> AppSession:
    with Session(connection.get_engine()) as session:
        return session.get(AppSession, session_id)


def _job_row(job_id: str) -> Job:
    with Session(connection.get_engine()) as session:
        return session.get(Job, job_id)


def test_interrupted_session_becomes_investigate(tmp_db):
    """An AppSession left RUNNING by a kill -9 is the gap this audit item is
    about: the run never finished, so `investigate` (not passed/failed) is
    the honest terminal state, and triage is the next step."""
    sid = _seed_session(SessionStatus.RUNNING)
    with Session(connection.get_engine()) as session:
        closed = SessionRepository(session).mark_running_interrupted(RESTART_REASON)
    assert closed == [sid]
    row = _session_row(sid)
    assert row.status == SessionStatus.INVESTIGATE
    assert row.ended_at is not None
    assert row.actual_outcome == RESTART_REASON


def test_session_sweep_never_touches_terminal_rows(tmp_db):
    """Already-terminal sessions keep their real outcome — recovery must not
    rewrite history."""
    done = _seed_session(SessionStatus.PASSED, "Tester: done")
    _seed_session(SessionStatus.FAILED, "Tester: failed")
    with Session(connection.get_engine()) as session:
        closed = SessionRepository(session).mark_running_interrupted(RESTART_REASON)
    assert closed == []
    assert _session_row(done).status == SessionStatus.PASSED


def test_unified_recovery_closes_all_three_job_types(tmp_db):
    """The point of unifying: one call closes BuildLog, Job and AppSession,
    and reports each so the startup log says what happened."""
    build = _seed_build("b-stuck", completed=False)
    job = _seed_job(JobState.RUNNING, "j-stuck")
    sid = _seed_session(SessionStatus.RUNNING)

    with Session(connection.get_engine()) as session:
        report = recover_interrupted_work(session)

    assert report == RecoveryReport(builds=1, jobs=1, sessions=1)
    assert report.total == 3
    assert "1 session(s)" in report.describe()

    with Session(connection.get_engine()) as session:
        assert BuildLogRepository(session).get(build).success is False
    assert _job_row(job).status == JobState.ABANDONED
    assert _session_row(sid).status == SessionStatus.INVESTIGATE


def test_recovery_is_a_noop_on_a_healthy_db(tmp_db):
    """The common boot must be cheap and silent."""
    _seed_build("b-done", completed=True)
    _seed_job(JobState.SUCCEEDED, "j-done")
    _seed_session(SessionStatus.PASSED, "Tester: done")
    with Session(connection.get_engine()) as session:
        report = recover_interrupted_work(session)
    assert report.total == 0


def test_boot_recovers_all_three_types(tmp_db):
    """End-to-end: rows left in flight by a fake crash are all closed by a
    fresh app lifespan."""
    from fastapi.testclient import TestClient

    from app.main import app

    _seed_build("b-crash", completed=False)
    _seed_job(JobState.RUNNING, "j-crash")
    sid = _seed_session(SessionStatus.RUNNING)
    assert _session_row(sid).status == SessionStatus.RUNNING

    with TestClient(app):  # lifespan startup runs the unified recovery
        pass

    with Session(connection.get_engine()) as session:
        assert BuildLogRepository(session).get("b-crash").success is False
    assert _job_row("j-crash").status == JobState.ABANDONED
    assert _session_row(sid).status == SessionStatus.INVESTIGATE
