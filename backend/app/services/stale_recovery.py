"""Stale-running recovery for every in-flight job type (audit Batch 2).

Three tables can hold a row claiming work is in flight:

- `BuildLog` — a build's own row, `completed_at IS NULL` while it runs.
- `Job` — the generic ledger every submitted job opens (audit B5),
  `queued`/`running` while it runs.
- `AppSession` — a scripted tester's session, `status=RUNNING` while it runs.

An interrupt that skips the graceful drain (audit B7) — a `kill -9`, a
crash, a container stop — leaves all three reading "in flight" forever.
BuildLog and Job each had a sweep, wired from a different place with a
different policy; AppSession had none at all, which is why a killed tester
run showed "Working…" across restarts long after the v1.17.8.3 BuildLog
lesson was learned. One policy, one call site.

Deliberately **not** a beat: recovery is a boot-time fact, not periodic
work, and it must not race a legitimately running job. `main.lifespan`
calls it before the scheduler starts.

Why this is the *startup* sweep only: at shutdown (audit B7) workers are
never cancelled, so a build or tester can still reach its own `end()` and
write the true terminal state afterwards. Closing those tables at shutdown
would flap — exactly the failure B7's terminal-state guard fixed for `Job`.
Job is safe either way because of that guard, so the drain closes Job
itself; anything else waits for the next boot, where no worker can
contradict it.
"""

from dataclasses import dataclass

from sqlmodel import Session

from app.core.logging import get_logger
from app.repositories.build import BuildLogRepository
from app.repositories.job import JobRepository
from app.repositories.session import SessionRepository

logger = get_logger(__name__)

# Written onto every row this closes, so the ledger says *why* it stopped
# rather than leaving the reader to guess.
RESTART_REASON = "Aborted: Sentinel restarted before the work finished."


@dataclass(frozen=True)
class RecoveryReport:
    """What one recovery pass closed out, per job type."""

    builds: int = 0
    jobs: int = 0
    sessions: int = 0

    @property
    def total(self) -> int:
        return self.builds + self.jobs + self.sessions

    def describe(self) -> str:
        """Human summary for the startup log / activity feed."""
        return (
            f"{self.builds} build(s), {self.jobs} job(s), "
            f"{self.sessions} session(s) left in flight"
        )


def recover_interrupted_work(
    session: Session, reason: str = RESTART_REASON
) -> RecoveryReport:
    """Close out every row still claiming to be in flight (audit Batch 2).

    Idempotent, and safe to call with nothing stale (the common boot).
    The caller owns the session, so recovery runs inside the lifespan's own
    transaction instead of opening a second one against the same file.
    """
    builds = BuildLogRepository(session).mark_orphaned_as_failed(reason)
    jobs = JobRepository(session).abandon_unfinished(reason)
    sessions = SessionRepository(session).mark_running_interrupted(reason)
    report = RecoveryReport(builds=builds, jobs=len(jobs), sessions=len(sessions))
    if report.total:
        logger.info("Stale-running recovery closed out %s", report.describe())
    return report
