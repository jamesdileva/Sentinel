"""Generic job lifecycle repository (v1.17.19.11, audit B5)."""

import datetime

from sqlmodel import select

from app.db.models import Job, JobState
from app.repositories.base import Repository

# Storage caps (B5/B6): the one-liner stays poll-light and the stack stays
# debuggable without bloating the row. Truncation lives here so every
# caller gets it, not just the scheduler.
_ERROR_MAX_CHARS = 2000
_TRACEBACK_MAX_CHARS = 8000

_TERMINAL_STATES = (
    JobState.SUCCEEDED,
    JobState.FAILED,
    JobState.CANCELLED,
    JobState.ABANDONED,
)


def _terminal(job: Job) -> bool:
    """A lifecycle is a state machine: once a job has a terminal state, that
    is its answer. v1.17.19.13 (audit B7) — without this, a worker that
    finished *after* shutdown wrote `abandoned` over (or was overwritten by)
    would make the row flap between states and the Jobs view would lie in
    both directions. The drain timeout is the policy that decides which
    terminal state a job gets, not a race between two writes."""
    return job.status in _TERMINAL_STATES


class JobRepository(Repository):
    model = Job

    def create(self, job_id: str, job_type: str, project_id: str | None) -> Job:
        """Open a queued job row. Commits — the scheduler calls this from
        short-lived sessions on both request and worker threads."""
        job = Job(id=job_id, type=job_type, project_id=project_id)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def mark_running(self, job_id: str) -> Job | None:
        """Move queued -> running. Returns None when the row is gone (beats
        and foreign submit paths never open one — not an error)."""
        job = self.session.get(Job, job_id)
        if job is None:
            return None
        job.status = JobState.RUNNING
        job.started_at = datetime.datetime.now(datetime.timezone.utc)
        self.session.add(job)
        self.session.commit()
        return job

    def mark_succeeded(self, job_id: str, result_ref: str | None = None) -> Job | None:
        """Move -> succeeded with an optional pointer at the domain record
        the task produced (TestResult id, AppSession id, ...).

        No-op on an already-terminal row: a job closed out as abandoned at
        shutdown keeps that answer (B7)."""
        job = self.session.get(Job, job_id)
        if job is None or _terminal(job):
            return job
        job.status = JobState.SUCCEEDED
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        job.result_ref = result_ref
        self.session.add(job)
        self.session.commit()
        return job

    def mark_failed(
        self,
        job_id: str,
        error: str,
        error_type: str | None = None,
        traceback: str | None = None,
    ) -> Job | None:
        """Move -> failed, keeping the one-liner plus structured detail (B6:
        exception class for filtering, full stack for diagnosis).

        No-op on an already-terminal row, for the same reason as
        `mark_succeeded` (B7)."""
        job = self.session.get(Job, job_id)
        if job is None or _terminal(job):
            return job
        job.status = JobState.FAILED
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        job.error = error[:_ERROR_MAX_CHARS]
        job.error_type = error_type
        job.traceback = (
            traceback[:_TRACEBACK_MAX_CHARS] if traceback is not None else None
        )
        self.session.add(job)
        self.session.commit()
        return job

    def mark_cancelled(self, job_id: str) -> Job | None:
        """Move a never-started job -> cancelled. Only valid from queued:
        a running job's terminal transition belongs to its worker, which
        would otherwise be overwritten by a racing cancel."""
        job = self.session.get(Job, job_id)
        if job is None or job.status != JobState.QUEUED:
            return None
        job.status = JobState.CANCELLED
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        self.session.add(job)
        self.session.commit()
        return job

    def abandon_unfinished(self, reason: str) -> list[str]:
        """Close out every non-terminal job as abandoned (audit B7).

        Used on shutdown (drain timeout expired) and at startup (a restart
        killed the worker), so a row can never sit "running" forever and the
        Jobs view cannot lie about what is happening. Terminal rows are never
        touched. Returns the ids closed out.
        """
        abandoned = list(
            self.session.exec(
                select(Job).where(
                    Job.status.in_(
                        [
                            JobState.QUEUED,
                            JobState.RUNNING,
                        ]
                    )
                )
            ).all()
        )
        finished = datetime.datetime.now(datetime.timezone.utc)
        for job in abandoned:
            job.status = JobState.ABANDONED
            job.completed_at = finished
            job.error = reason[:_ERROR_MAX_CHARS]
            job.error_type = "AbandonedJob"
        if abandoned:
            self.session.commit()
        return [job.id for job in abandoned]

    def get_by_project(self, project_id: str, limit: int = 50) -> list[Job]:
        """Newest jobs for one project (future Jobs UI; B5 exposes by-id)."""
        stmt = (
            select(Job)
            .where(Job.project_id == project_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(stmt).all())
