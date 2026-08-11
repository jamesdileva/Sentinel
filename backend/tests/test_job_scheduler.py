"""Sprint 16: in-process JobScheduler (replaces Celery + Redis).

The scheduler owns the periodic beats (repo-sync, security-scan-all,
world-sim-tick) and the on-demand thread pool. Tests here are hermetic:
they exercise a fresh instance in inline mode and assert beat registration
without letting timers fire.
"""

import pytest

from app.core.config import settings
from app.services.job_scheduler import JobScheduler, _build_registry

EXPECTED_TASKS = {
    "run_build",
    "run_tests",
    "run_security_scan",
    "run_security_scan_all",
    "run_index_knowledge",
    "run_reset_knowledge",
    "run_repo_sync",
    "world_sim_tick",
}


def test_registry_exposes_all_task_names():
    assert set(_build_registry()) == EXPECTED_TASKS


def test_submit_inline_runs_synchronously(monkeypatch):
    """Inline mode (tests) executes the task on the calling thread and
    returns a job id before submit returns — the API's old eager contract."""
    scheduler = JobScheduler()
    scheduler.run_inline = True
    ran: list[str] = []

    def fake_task(project_id: str) -> dict:
        ran.append(project_id)
        return {"project_id": project_id}

    monkeypatch.setattr(scheduler, "_registry", {"fake_task": fake_task})
    job_id = scheduler.submit("fake_task", args=["p1"])
    assert ran == ["p1"]
    assert isinstance(job_id, str) and job_id
    scheduler.shutdown()


def test_submit_async_preserves_task_id():
    scheduler = JobScheduler()
    job_id = scheduler.submit("run_security_scan", args=["p1"], task_id="t-1")
    assert job_id == "t-1"
    scheduler.shutdown()


def test_submit_unknown_task_raises():
    scheduler = JobScheduler()
    try:
        with pytest.raises(KeyError):
            scheduler.submit("no_such_task")
    finally:
        scheduler.shutdown()


def test_submit_async_does_not_block_on_error():
    """A throwing task in pool mode must not raise in submit and must not
    kill later submits."""
    scheduler = JobScheduler(pool_size=1)
    scheduler.run_inline = False

    def boom() -> None:
        raise RuntimeError("boom")

    monkeypatch_replace(scheduler, "boom", boom)
    scheduler.submit("boom")
    ok = scheduler.submit("run_security_scan", args=["p1"])
    assert ok
    scheduler.shutdown()


def test_beats_registered_with_config_intervals(monkeypatch):
    monkeypatch.setattr(settings, "world_sim_enabled", True)
    scheduler = JobScheduler()
    scheduler.start()
    try:
        jobs = scheduler.beat_jobs
        assert "repo-sync" in jobs
        assert "nightly-security-scan" in jobs
        assert "world-sim-tick" in jobs
        from datetime import timedelta

        assert jobs["repo-sync"].trigger.interval == timedelta(
            minutes=settings.sync_interval_minutes
        )
        assert jobs["nightly-security-scan"].trigger.interval == timedelta(
            minutes=settings.schedule_interval_minutes
        )
    finally:
        scheduler.shutdown()


def test_beats_skip_world_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "world_sim_enabled", False)
    scheduler = JobScheduler()
    scheduler.start()
    try:
        ids = scheduler.beat_job_ids
        assert "world-sim-tick" not in ids
        assert "repo-sync" in ids
    finally:
        scheduler.shutdown()


def test_start_is_idempotent_shutdown_is_safe():
    scheduler = JobScheduler()
    scheduler.start()
    scheduler.start()  # must not double-register beats
    assert len(scheduler.beat_jobs) <= 3
    scheduler.shutdown()
    scheduler.shutdown()  # second shutdown must not raise


def test_quiet_beat_publishes_no_events(monkeypatch):
    """v1.17.4: the world-sim tick fires every minute; its beat publishes no
    activity events (running/finished/failed) so the live feed is not
    flooded. The task itself still runs."""
    from app.services import activity_bus

    events: list[str] = []
    monkeypatch.setattr(
        activity_bus, "publish_event", lambda *a, **k: events.append(a[1])
    )
    scheduler = JobScheduler()
    monkeypatch_replace(scheduler, "world_sim_tick", lambda: {"days_advanced": 0})
    try:
        scheduler._beat("world_sim_tick", quiet=True)()
        assert events == []
    finally:
        scheduler.shutdown()


def test_noisy_beat_and_submits_still_publish(monkeypatch):
    """On-demand jobs and non-quiet beats keep their events: downloads,
    scans and syncs are user-visible work, unlike minute-level world ticks."""
    from app.services import activity_bus

    events: list[str] = []
    monkeypatch.setattr(
        activity_bus, "publish_event", lambda *a, **k: events.append(a[1])
    )
    scheduler = JobScheduler()
    monkeypatch_replace(scheduler, "fake_beat", lambda: {"ok": True})
    try:
        scheduler._beat("fake_beat")()
        assert any("running" in e for e in events)
        assert any("finished" in e for e in events)
    finally:
        scheduler.shutdown()


def monkeypatch_replace(scheduler, name, func):
    """Swap a registry entry without touching the class registry."""
    scheduler._registry[name] = func
