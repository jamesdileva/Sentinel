"""Generic job lifecycle repository (v1.17.19.11, audit B5)."""

import datetime

from sqlmodel import select

from app.db.models import Job, JobState
from app.repositories.base import Repository


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
        the task produced (TestResult id, AppSession id, ...)."""
        job = self.session.get(Job, job_id)
        if job is None:
            return None
        job.status = JobState.SUCCEEDED
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        job.result_ref = result_ref
        self.session.add(job)
        self.session.commit()
        return job

    def mark_failed(self, job_id: str, error: str) -> Job | None:
        """Move -> failed, keeping a one-line error (B6 enriches this)."""
        job = self.session.get(Job, job_id)
        if job is None:
            return None
        job.status = JobState.FAILED
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        job.error = error
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

    def get_by_project(self, project_id: str, limit: int = 50) -> list[Job]:
        """Newest jobs for one project (future Jobs UI; B5 exposes by-id)."""
        stmt = (
            select(Job)
            .where(Job.project_id == project_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(stmt).all())
