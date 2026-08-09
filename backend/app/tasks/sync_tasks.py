"""Scheduled repo sync task (Sprint 12.1).

Runs `RepoSyncService.sync()` on the in-process beat schedule defined by
`SENTINEL_SYNC_INTERVAL_MINUTES`. Opens its own DB session, same pattern as
app/tasks/build_tasks.py.
"""

from app.core.logging import get_logger
from app.services.sync_service import run_sync

logger = get_logger(__name__)


def run_repo_sync() -> dict:
    """Clone/pull GitHub repos into watch dirs, then re-index (Rule 3 deterministic)."""
    logger.info("repo sync task starting")
    result = run_sync()
    logger.info(
        "repo sync done: %d cloned, %d updated, %d failed",
        len(result.get("cloned", [])),
        len(result.get("pulled", [])),
        len(result.get("failed", {})),
    )
    return result
