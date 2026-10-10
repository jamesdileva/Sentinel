"""In-process job scheduler — replaces Celery + Redis (Sprint 16, docs/02 §7).

Sentinel now runs as a single process (uvicorn) with no broker or worker
containers:
- APScheduler `BackgroundScheduler` runs the periodic beats that Celery beat
  used to own: repo sync, the daily security scan-all and the world-sim tick.
  Since v1.17.7 the scan-all is its own beat (`SENTINEL_SCAN_INTERVAL_MINUTES`)
  instead of the final step of the repo-sync pass, so a tokenless install
  (all projects already local, no GitHub) still scans on schedule. The
  `repo-sync` beat registers only when `SENTINEL_GITHUB_TOKEN` is set.
- A small `ThreadPoolExecutor` runs on-demand jobs (build / test / scan /
  knowledge index) submitted by the API, preserving the poll-by-job_id
  envelope semantics (`JobStatus`, `JobEnvelope`).

The task functions in `app/tasks/*` are plain callables registered here by
name. Tests drive them directly (no broker, eager by construction).
"""

import threading
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.logging import get_logger
from app.services import activity_bus

logger = get_logger(__name__)

_BEAT_IDS = ("repo-sync", "scan-all", "world-sim-tick")

# Registry task name -> generic job family (audit B5). The family is what the
# Jobs UI groups by: scan and scan-all are both "security". Unmapped names
# (test fakes) fall back to the raw task name — never invent a project id
# for those; foreign keys are enforced, so a guessed id would 500 the submit.
_JOB_TYPES = {
    "run_build": "build",
    "run_tests": "test",
    "run_tester": "tester",
    "run_security_scan": "security",
    "run_security_scan_all": "security",
    "run_index_knowledge": "knowledge",
    "run_index_knowledge_all": "knowledge",
    "run_reset_knowledge": "knowledge",
    "run_repo_sync": "sync",
    "world_sim_tick": "world_sim",
}

# Task-result dict keys that point at the domain record a job produced,
# in preference order. Builds return their own job id (the API pre-creates
# the BuildLog under it); tests return the TestResult id; testers the
# AppSession id. Anything else leaves result_ref empty.
_RESULT_REF_KEYS = ("result_ref", "session_id", "job_id")

# Length caps for failure text live in repositories/job.py (single storage
# policy for every caller, B5/B6).


def _build_registry() -> dict[str, Callable]:
    """Maps task names (previously Celery task ids) to plain callables."""
    from app.tasks import (
        build_tasks,
        rag_tasks,
        sync_tasks,
        tester_tasks,
        world_sim_tasks,
    )

    return {
        "run_build": build_tasks.run_build_task,
        "run_tests": build_tasks.run_tests_task,
        "run_tester": tester_tasks.run_tester_task,
        "run_security_scan": build_tasks.run_security_scan_task,
        "run_security_scan_all": build_tasks.run_security_scan_all,
        "run_index_knowledge": rag_tasks.run_index_knowledge,
        "run_index_knowledge_all": rag_tasks.run_index_knowledge_all,
        "run_reset_knowledge": rag_tasks.run_reset_knowledge,
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
        # (name, job_id, future) for on-demand jobs still queued in the pool
        # (v1.17.7.2) — lets a reset cancel pending re-index jobs instead of
        # re-embedding immediately after the flags were cleared. The job_id
        # (v1.17.19.11, B5) lets cancellation close out the persisted row.
        self._pending: list[tuple[str, str, Future]] = []
        self._lock = threading.Lock()

    # -- jobs bridged by routers ---------------------------------------------

    def submit(
        self,
        name: str,
        args: list | None = None,
        task_id: str | None = None,
        project_id: str | None = None,
        job_type: str | None = None,
    ) -> str:
        """Resolve an on-demand task and return its job id.

        `args` must be JSON-safe (they are persisted in job rows by callers).
        Mirrors the old `apply_async(task_id=...)` envelope. In inline mode
        (tests) the task runs synchronously before this returns.

        v1.17.19.11 (audit B5): opens the persisted Job row (queued) so every
        submitted job shares one pollable lifecycle, whatever its task. Beats
        bypass submit (they call `_run` directly) and get no row — periodic
        system work is not user-trackable. Bookkeeping must never break the
        job itself, so a failed write logs and the submit proceeds.
        """
        job_id = task_id or str(uuid.uuid4())
        func = self._registry[name]
        _record_submit(job_id, job_type or _JOB_TYPES.get(name, name), project_id)
        if self.run_inline:
            self._run(job_id, name, func, args or [])
            return job_id
        logger.info("job %s (%s) submitted", job_id, name)
        activity_bus.publish_event(
            "job",
            f"{name} queued",
            detail=f"job {job_id}",
            data={"job_id": job_id, "name": name, "state": "queued"},
        )
        future = self._executor.submit(self._run, job_id, name, func, args or [])
        with self._lock:
            self._pending.append((name, job_id, future))
        future.add_done_callback(self._discard)
        return job_id

    def _discard(self, future: Future) -> None:
        with self._lock:
            self._pending[:] = [
                (name, job_id, f)
                for name, job_id, f in self._pending
                if f is not future
            ]

    def cancel_queued(self, name_prefix: str) -> int:
        """Cancel queued (not yet started) jobs whose task name starts with
        `name_prefix` (v1.17.7.2). Returns the number cancelled; jobs already
        running in the pool are untouched.

        v1.17.19.11 (audit B5): successfully cancelled jobs also close out
        their persisted row as cancelled, so they stop looking queued forever.
        Only futures `cancel()` actually stops are marked — a running job's
        terminal transition belongs to its worker.
        """
        with self._lock:
            pending = list(self._pending)
        cancelled: list[str] = []
        for name, job_id, future in pending:
            if name.startswith(name_prefix) and future.cancel():
                cancelled.append(job_id)
        with self._lock:
            self._pending = [
                (name, job_id, future)
                for name, job_id, future in self._pending
                if not (name.startswith(name_prefix) and future.cancelled())
            ]
        if cancelled:
            logger.info("cancelled %d queued %r job(s)", len(cancelled), name_prefix)
            _record_cancelled(cancelled)
        return len(cancelled)

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start (idempotently) the background beats. Never blocks; scheduled
        jobs run in thread pool threads the scheduler owns."""
        if self._started:
            return
        if settings.world_sim_enabled:
            self._beats.add_job(
                self._beat("world_sim_tick", quiet=True),
                IntervalTrigger(seconds=settings.world_sim_tick_seconds),
                id="world-sim-tick",
                name="world-sim-tick",
                replace_existing=True,
            )
        # v1.17.7: scan-all owns its own schedule (a tokenless install still
        # scans daily); repo-sync is GitHub-gated and needs the token.
        self._beats.add_job(
            self._beat("run_security_scan_all"),
            IntervalTrigger(minutes=settings.scan_interval_minutes),
            id="scan-all",
            name="scan-all",
            replace_existing=True,
        )
        if settings.github_token:
            self._beats.add_job(
                self._beat("run_repo_sync"),
                IntervalTrigger(minutes=settings.sync_interval_minutes),
                id="repo-sync",
                name="repo-sync",
                replace_existing=True,
            )
        self._beats.start()
        self._started = True
        logger.info(
            "In-process scheduler started (sync=%dmin scan=%dmin world=%ds)",
            settings.sync_interval_minutes,
            settings.scan_interval_minutes,
            settings.world_sim_tick_seconds,
        )

    def shutdown(self) -> None:
        """Stop beats and release the job pool (v1.17.6).

        Running and queued jobs drain to completion: `cancel_futures=True`
        used to kill an in-flight knowledge index mid-upsert, guaranteeing
        the exact on-disk Chroma corruption (Nothing found on disk) this
        release detects and recovers from. `wait=False` keeps uvicorn's
        shutdown synchronous — the workers just keep flushing quietly."""
        if self._started:
            self._beats.shutdown(wait=False)
            self._started = False
        self._executor.shutdown(wait=False, cancel_futures=False)
        logger.info("In-process scheduler stopped")

    # -- internals -----------------------------------------------------------

    def _beat(self, name: str, quiet: bool = False) -> Callable:
        """Wrap a task as a scheduler beat. `quiet=True` (v1.17.4: the
        world-sim tick) suppresses its running/finished/failed activity
        events — a tick fires every minute and would otherwise flood the
        live feed; the per-tick log line is unaffected."""
        func = self._registry[name]

        def wrapper() -> None:
            self._run("beat:" + name, name, func, [], publish_events=not quiet)

        return wrapper

    @staticmethod
    def _run(
        job_id: str,
        name: str,
        func: Callable,
        args: list,
        publish_events: bool = True,
    ) -> None:
        """Execute one job, moving its persisted row through the lifecycle.

        v1.17.19.11 (audit B5): running on entry, succeeded (with the task's
        domain pointer, when it returns one) or failed (with a one-line error)
        on exit. Rows are looked up, never assumed: beats call this directly
        with synthetic ids and get no row, which is deliberate.
        """
        _record_running(job_id)
        if publish_events:
            activity_bus.publish_event(
                "job",
                f"{name} running",
                detail=f"job {job_id}",
                data={"job_id": job_id, "name": name, "state": "running"},
            )
        try:
            result = func(*args)
            logger.info("%s (%s) finished: %r", name, job_id, result)
            _record_succeeded(job_id, _result_ref(result))
            if publish_events:
                activity_bus.publish_event(
                    "job",
                    f"{name} finished",
                    detail=f"job {job_id}",
                    data={"job_id": job_id, "name": name, "state": "finished"},
                )
        except (
            Exception
        ) as exc:  # noqa: BLE001 — a worker job must never crash the process
            logger.exception("%s (%s) failed", name, job_id)
            _record_failed(
                job_id,
                f"{type(exc).__name__}: {exc}",
                error_type=type(exc).__name__,
                traceback=traceback.format_exc(),
            )
            if publish_events:
                activity_bus.publish_event(
                    "job",
                    f"{name} failed",
                    detail=f"job {job_id}",
                    data={"job_id": job_id, "name": name, "state": "failed"},
                )

    @property
    def beat_jobs(self) -> dict:
        return {job.id: job for job in self._beats.get_jobs()}

    @property
    def beat_job_ids(self) -> list[str]:
        return list(self.beat_jobs)


def _session():
    """A short-lived session for job bookkeeping (never the request's)."""
    from sqlmodel import Session

    from app.db.connection import get_engine

    return Session(get_engine())


def _record_submit(job_id: str, job_type: str, project_id: str | None) -> None:
    """Open the queued row. Best-effort by design: the pool work matters more
    than the ledger, so a failed write logs loudly and the submit proceeds."""
    try:
        from app.repositories.job import JobRepository

        with _session() as session:
            JobRepository(session).create(job_id, job_type, project_id)
    except Exception:  # noqa: BLE001 — bookkeeping must not break submission
        logger.warning("job ledger unavailable at submit for %s", job_id, exc_info=True)


def _record_running(job_id: str) -> None:
    try:
        from app.repositories.job import JobRepository

        with _session() as session:
            JobRepository(session).mark_running(job_id)
    except Exception:  # noqa: BLE001
        logger.warning("job ledger unavailable at start for %s", job_id, exc_info=True)


def _record_succeeded(job_id: str, result_ref: str | None) -> None:
    try:
        from app.repositories.job import JobRepository

        with _session() as session:
            JobRepository(session).mark_succeeded(job_id, result_ref)
    except Exception:  # noqa: BLE001
        logger.warning("job ledger unavailable at finish for %s", job_id, exc_info=True)


def _record_failed(
    job_id: str,
    error: str,
    error_type: str | None = None,
    traceback: str | None = None,
) -> None:
    """Persist the failure. Length caps live in the repository (single
    storage policy for every caller); this function just must not lose the
    stack on the way there."""
    try:
        from app.repositories.job import JobRepository

        with _session() as session:
            JobRepository(session).mark_failed(
                job_id, error, error_type=error_type, traceback=traceback
            )
    except Exception:  # noqa: BLE001
        logger.warning("job ledger unavailable at fail for %s", job_id, exc_info=True)


def _record_cancelled(job_ids: list[str]) -> None:
    try:
        from app.repositories.job import JobRepository

        with _session() as session:
            repo = JobRepository(session)
            for job_id in job_ids:
                repo.mark_cancelled(job_id)
    except Exception:  # noqa: BLE001
        logger.warning("job ledger unavailable at cancel", exc_info=True)


def _result_ref(result: object) -> str | None:
    """Pull the task's domain pointer out of its return dict, if it gave one."""
    if not isinstance(result, dict):
        return None
    for key in _RESULT_REF_KEYS:
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    return None


scheduler = JobScheduler()
