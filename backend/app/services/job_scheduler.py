"""In-process job scheduler — replaces Celery + Redis (Sprint 16, docs/02 §7).

Sentinel now runs as a single process (uvicorn) with no broker or worker
containers:
- APScheduler `BackgroundScheduler` runs the periodic beats that Celery beat
  used to own: repo sync, security scan-all, world-sim tick.
- A small `ThreadPoolExecutor` runs on-demand jobs (build / test / scan /
  knowledge index) submitted by the API, preserving the poll-by-job_id
  envelope semantics (`JobStatus`, `JobEnvelope`).

The task functions in `app/tasks/*` are plain callables registered here by
name. Tests drive them directly (no broker, eager by construction).
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BEAT_IDS = ("repo-sync", "nightly-security-scan", "world-sim-tick")


def _build_registry() -> dict[str, Callable]:
    """Maps task names (previously Celery task ids) to plain callables."""
    from app.tasks import build_tasks, rag_tasks, sync_tasks, world_sim_tasks

    return {
        "run_build": build_tasks.run_build_task,
        "run_tests": build_tasks.run_tests_task,
        "run_security_scan": build_tasks.run_security_scan_task,
        "run_security_scan_all": build_tasks.run_security_scan_all,
        "run_index_knowledge": rag_tasks.run_index_knowledge,
        "run_repo_sync": sync_tasks.run_repo_sync,
        "world_sim_tick": world_sim_tasks.world_sim_tick,
    }


class JobScheduler:
    """Owns the periodic beats and the on-demand job thread pool."""

    def __init__(self, pool_size: int = 2) -> None:
        self._registry = _build_registry()
        self._executor = ThreadPoolExecutor(
            max_workers=pool_size, thread_name_prefix="sentinel-job"
        )
        self._beats = BackgroundScheduler()
        self._started = False
        # Tests flip this to True so jobs run synchronously on the calling
        # thread (replaces the old Celery `task_always_eager` escape hatch).
        self.run_inline = False

    # -- jobs bridged by routers ---------------------------------------------

    def submit(
        self, name: str, args: list | None = None, task_id: str | None = None
    ) -> str:
        """Resolve an on-demand task and return its job id.

        `args` must be JSON-safe (they are persisted in job rows by callers).
        Mirrors the old `apply_async(task_id=...)` envelope. In inline mode
        (tests) the task runs synchronously before this returns.
        """
        job_id = task_id or str(uuid.uuid4())
        func = self._registry[name]
        if self.run_inline:
            self._run(job_id, name, func, args or [])
            return job_id
        logger.info("job %s (%s) submitted", job_id, name)
        self._executor.submit(self._run, job_id, name, func, args or [])
        return job_id

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start (idempotently) the background beats. Never blocks; scheduled
        jobs run in thread pool threads the scheduler owns."""
        if self._started:
            return
        if settings.world_sim_enabled:
            self._beats.add_job(
                self._beat("world_sim_tick"),
                IntervalTrigger(seconds=settings.world_sim_tick_seconds),
                id="world-sim-tick",
                name="world-sim-tick",
                replace_existing=True,
            )
        self._beats.add_job(
            self._beat("run_repo_sync"),
            IntervalTrigger(minutes=settings.sync_interval_minutes),
            id="repo-sync",
            name="repo-sync",
            replace_existing=True,
        )
        self._beats.add_job(
            self._beat("run_security_scan_all"),
            IntervalTrigger(minutes=settings.schedule_interval_minutes),
            id="nightly-security-scan",
            name="nightly-security-scan",
            replace_existing=True,
        )
        self._beats.start()
        self._started = True
        logger.info(
            "In-process scheduler started (sync=%dmin scan=%dmin world=%ds)",
            settings.sync_interval_minutes,
            settings.schedule_interval_minutes,
            settings.world_sim_tick_seconds,
        )

    def shutdown(self) -> None:
        if self._started:
            self._beats.shutdown(wait=False)
            self._started = False
        self._executor.shutdown(wait=False, cancel_futures=True)
        logger.info("In-process scheduler stopped")

    # -- internals -----------------------------------------------------------

    def _beat(self, name: str) -> Callable:
        func = self._registry[name]

        def wrapper() -> None:
            self._run("beat:" + name, name, func, [])

        return wrapper

    @staticmethod
    def _run(job_id: str, name: str, func: Callable, args: list) -> None:
        try:
            result = func(*args)
            logger.info("%s (%s) finished: %r", name, job_id, result)
        except Exception:  # noqa: BLE001 — a worker job must never crash the process
            logger.exception("%s (%s) failed", name, job_id)

    @property
    def beat_jobs(self) -> dict:
        return {job.id: job for job in self._beats.get_jobs()}

    @property
    def beat_job_ids(self) -> list[str]:
        return list(self.beat_jobs)


scheduler = JobScheduler()