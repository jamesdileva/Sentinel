"""GitHistoryService — parse git log into GitCommit rows (docs/02 §3.7, minimal).

Deterministic subprocess parser: reads `git log` output via `run_command` and
maps it onto the GitCommit table. Feature classification and timeline
extraction are deferred to a later sprint.
"""

import datetime

from sqlmodel import Session

from app.core.logging import get_logger
from app.db.models import GitCommit, Project
from app.repositories import GitCommitRepository, ProjectRepository
from app.services.command_runner import run_command

logger = get_logger(__name__)

_LOG_FORMAT = "%H|%an|%aI|%s"
_MAX_COMMITS = 100


def parse_log(text: str) -> list[dict]:
    """Parse `git log --pretty=format:<LOG_FORMAT>` output into commit dicts.

    Pure function (no I/O) so it is unit-testable without a git repository.
    """
    commits: list[dict] = []
    for line in text.splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        commit_hash, author, iso_date, message = parts
        if not commit_hash or not message:
            continue
        try:
            timestamp = datetime.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        except ValueError:
            timestamp = None
        commits.append(
            {
                "hash": commit_hash,
                "author": author or None,
                "timestamp": timestamp,
                "message": message,
            }
        )
    return commits


class GitHistoryService:
    """Analyzes git history for a project and persists GitCommit rows."""

    def __init__(self, session: Session):
        self.session = session

    def analyze_history(self, project: Project) -> list[GitCommit]:
        """Run `git log` and persist commits, skipping already-known hashes."""
        result = run_command(
            f'git -C "{project.path}" log --pretty=format:"{_LOG_FORMAT}" '
            f"--max-count={_MAX_COMMITS}"
        )
        if result.exit_code != 0:
            logger.warning(
                "git log failed for %s: %s", project.path, result.stderr[:300]
            )
            return []

        existing = GitCommitRepository(self.session).hashes_for_project(project.id)
        saved: list[GitCommit] = []
        for item in parse_log(result.stdout):
            if item["hash"] in existing:
                continue
            row = GitCommit(project_id=project.id, **item)
            self.session.add(row)
            saved.append(row)
        self.session.commit()
        logger.info("Git history for %s: %d new commit(s)", project.name, len(saved))
        return saved

    @staticmethod
    def get_project(session: Session, project_id: str) -> Project:
        project = ProjectRepository(session).get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        return project
