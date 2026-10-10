"""Audit B5: generic persisted jobs (v1.17.19.11).

Every scheduler-submitted job shares one pollable lifecycle — queued at
submit, running at start, succeeded/failed/cancelled at end — whatever
domain record its task also writes. Beats deliberately get no row.
"""

import threading

import pytest
from sqlmodel import Session

from app.db import connection
from app.db.models import JobState, Project
from app.repositories.job import JobRepository
from app.services.job_scheduler import JobScheduler


@pytest.fixture()
def scheduler():
    sched = JobScheduler(pool_size=1)
    try:
        yield sched
    finally:
        sched.shutdown()


@pytest.fixture()
def eager(monkeypatch):
    """Run the global scheduler's jobs synchronously so API tests need no
    threads (and never touch the pool executor, which TestClient lifespan
    shuts down between tests)."""
    from app.services import job_scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module.scheduler, "run_inline", True)
    yield
    monkeypatch.setattr(scheduler_module.scheduler, "run_inline", False)


def _project_id() -> str:
    with Session(connection.get_engine()) as session:
        project = Project(name="job-probe", path="/tmp/job-probe", language="python")
        session.add(project)
        session.commit()
        session.refresh(project)
        return project.id


def _row(job_id: str):
    with Session(connection.get_engine()) as session:
        return JobRepository(session).get(job_id)


def test_submit_opens_queued_row_then_completes(tmp_db, scheduler):
    """Inline submit runs the task synchronously; the row walks the full
    lifecycle in one call."""
    scheduler.run_inline = True
    scheduler._registry["fake_task"] = lambda: {"ok": True}
    job_id = scheduler.submit("fake_task")
    row = _row(job_id)
    assert row is not None
    assert row.type == "fake_task"  # unmapped names fall back to the task name
    assert row.project_id is None
    assert row.status == JobState.SUCCEEDED
    assert row.started_at is not None and row.completed_at is not None
    assert row.completed_at >= row.started_at >= row.created_at


def test_submit_records_type_and_project(tmp_db, scheduler):
    """Known task names map to families; the caller's project id is stored
    (foreign keys are enforced, so only real ids may be passed)."""
    scheduler.run_inline = True
    pid = _project_id()
    scheduler._registry["run_tests"] = lambda project_id: {"job_id": "r-1"}
    job_id = scheduler.submit("run_tests", args=[pid], project_id=pid)
    row = _row(job_id)
    assert row.type == "test"
    assert row.project_id == pid
    assert row.status == JobState.SUCCEEDED
    assert row.result_ref == "r-1"  # the task's TestResult pointer, kept


def test_result_ref_prefers_session_over_job_id(tmp_db, scheduler):
    """Tester tasks return both ids; the AppSession one is the useful domain
    pointer, so it wins."""
    scheduler.run_inline = True
    scheduler._registry["run_tester"] = lambda pid: {
        "job_id": "same-as-job",
        "session_id": "s-9",
    }
    job_id = scheduler.submit("run_tester", args=["p"])
    assert _row(job_id).result_ref == "s-9"


def test_failing_task_leaves_failed_row_with_error(tmp_db, scheduler):
    """A worker exception can no longer vanish into an activity event (this
    is the durable half of B6's problem; B5 records the one-liner)."""
    scheduler.run_inline = True

    def boom() -> None:
        raise RuntimeError("boom")

    scheduler._registry["boom"] = boom
    job_id = scheduler.submit("boom")
    row = _row(job_id)
    assert row.status == JobState.FAILED
    assert row.error is not None and "RuntimeError" in row.error and "boom" in row.error
    assert row.completed_at is not None
    # v1.17.19.12 (audit B6): the structured detail survives with it.
    assert row.error_type == "RuntimeError"
    assert row.traceback is not None
    assert "RuntimeError: boom" in row.traceback
    # A real stack, not just the message: scheduler frame plus task frame.
    assert "job_scheduler.py" in row.traceback
    assert "in boom" in row.traceback


def test_failure_traceback_is_truncated(tmp_db):
    """Deep stacks must not bloat the row or the /jobs poll (B6)."""
    from app.repositories.job import JobRepository

    with Session(connection.get_engine()) as session:
        repo = JobRepository(session)
        job = repo.create("j-trace", "test", None)
        repo.mark_failed(job.id, "x", error_type="E", traceback="T" * 9000)
    row = _row("j-trace")
    assert row is not None and row.traceback is not None
    assert len(row.traceback) == 8000


def test_beats_write_no_job_row(tmp_db, scheduler):
    """Periodic system work is not user-trackable: the beat path calls _run
    directly with a synthetic id and must not touch the ledger."""
    scheduler._registry["world_sim_tick"] = lambda: {"days_advanced": 0}
    scheduler._beat("world_sim_tick", quiet=True)()
    with Session(connection.get_engine()) as session:
        assert JobRepository(session).count() == 0


def test_cancel_queued_marks_row_cancelled(tmp_db, scheduler):
    """A future cancel() actually stops only reaches the pool-never-started
    case, so marking those rows cancelled is exact — the running job's own
    terminal transition is untouched."""
    started = threading.Event()
    release = threading.Event()

    def slow() -> None:
        started.set()
        release.wait(timeout=5)

    scheduler._registry["slow"] = slow
    scheduler._registry["work"] = lambda: {"ok": True}
    try:
        slow_id = scheduler.submit("slow")
        assert started.wait(timeout=5)
        queued_id = scheduler.submit("work")
        assert scheduler.cancel_queued("work") == 1
        cancelled = _row(queued_id)
        assert cancelled is not None and cancelled.status == JobState.CANCELLED
        assert cancelled.completed_at is not None
    finally:
        release.set()
    assert _terminal(slow_id).status == JobState.SUCCEEDED


def _terminal(job_id: str, timeout: float = 10.0):
    """Poll the ledger until the job leaves running (pool threads finish on
    their own schedule; asserting immediately after release would race)."""
    import time

    deadline = time.monotonic() + timeout
    while True:
        row = _row(job_id)
        assert row is not None
        if row.status != JobState.RUNNING:
            return row
        assert time.monotonic() < deadline, f"job {job_id} never finished"
        time.sleep(0.05)


def test_build_submit_creates_both_rows(client, tmp_db, eager, monkeypatch):
    """The API pre-creates the BuildLog under the job id; submit adds the
    generic row under the same id, so the two records stay joinable."""
    from app.services.build_runner import BuildRunner

    def _ok(self, project, log=None):
        log.success = True
        log.exit_code = 0
        return log

    monkeypatch.setattr(BuildRunner, "run_build", _ok)
    pid = _project_id()
    resp = client.post("/api/v1/builds/run", json={"project_id": pid})
    assert resp.status_code == 202
    job_id = resp.json()["id"]
    row = _row(job_id)
    assert row is not None
    assert (row.type, row.project_id) == ("build", pid)
    with Session(connection.get_engine()) as session:
        from app.db.models import BuildLog

        assert session.get(BuildLog, job_id) is not None


def test_jobs_endpoint_returns_row_and_404s(client, tmp_db, eager, monkeypatch):
    """GET /jobs/{id} is the uniform poll every envelope can point at."""
    from types import SimpleNamespace

    from app.services.test_runner import TestRunner

    monkeypatch.setattr(
        TestRunner,
        "run_tests",
        lambda self, project: SimpleNamespace(
            id="tr-1", passed=1, failed=0, errors=0, summary="ok"
        ),
    )
    pid = _project_id()
    resp = client.post("/api/v1/tests/run", params={"project_id": pid})
    assert resp.status_code == 202
    body = client.get(f"/api/v1/jobs/{resp.json()['job_id']}")
    assert body.status_code == 200
    payload = body.json()
    assert payload["type"] == "test" and payload["project_id"] == pid
    assert payload["status"] == "succeeded"
    assert payload["result_ref"] == "tr-1"
    assert client.get("/api/v1/jobs/does-not-exist").status_code == 404


def test_jobs_endpoint_exposes_failure_detail(client, tmp_db, eager, monkeypatch):
    """B6: the failed row's diagnosis is retrievable long after the
    announcing activity event has been pruned away."""
    from app.services.job_scheduler import scheduler as _global

    monkeypatch.setitem(_global._registry, "always_fails", _always_fails)
    job_id = _global.submit("always_fails")
    body = client.get(f"/api/v1/jobs/{job_id}")
    assert body.status_code == 200
    payload = body.json()
    assert payload["status"] == "failed"
    assert payload["error_type"] == "ValueError"
    assert "deliberate" in (payload["traceback"] or "")


def _always_fails() -> None:
    raise ValueError("deliberate test failure")


def test_jobs_listed_per_project(tmp_db, scheduler):
    """Repo helper for the future Jobs UI: newest-first, scoped to a project."""
    scheduler.run_inline = True
    scheduler._registry["t"] = lambda: {"ok": True}
    pid = _project_id()
    first = scheduler.submit("t", project_id=pid)
    second = scheduler.submit("t", project_id=pid)
    other = scheduler.submit("t")
    with Session(connection.get_engine()) as session:
        rows = JobRepository(session).get_by_project(pid)
    assert [r.id for r in rows] == [second, first]
    assert all(r.project_id == pid for r in rows)
    assert _row(other).project_id is None
