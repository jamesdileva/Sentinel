"""Scheduled repo sync task (Sprint 12.1).

Runs `RepoSyncService.sync()` on the in-process beat schedule defined by
`SENTINEL_SYNC_INTERVAL_MINUTES`. Since v1.17.7 the daily security scan-all
is its own beat (`scan-all`, `SENTINEL_SCAN_INTERVAL_MINUTES`) — the repo
sync only pulls and re-indexes. Opens its own DB session, same pattern as
app/tasks/build_tasks.py.
"""

from app.core.logging import get_logger
from app.services import activity_bus
from app.services.sync_service import run_sync

logger = get_logger(__name__)


def run_repo_sync() -> dict:
    """Clone/pull GitHub repos into watch dirs, then re-index (Rule 3
    deterministic). The security scan-all runs on its own beat (v1.17.7)."""
    logger.info("repo sync task starting")
    result = run_sync()
    if not result.get("configured"):
        # v1.17.7: tokenless is a supported setup (projects already local) —
        # say so plainly instead of "skipped".
        activity_bus.publish_event(
            "sync",
            "GitHub repo sync disabled — token not configured",
            detail=(
                "SENTINEL_GITHUB_TOKEN is not set; local projects are indexed "
                "directly from the watch dirs and the daily security scan runs "
                "on its own schedule."
            ),
            data={"configured": False},
        )
        return result
    cloned = result.get("cloned", [])
    pulled = result.get("pulled", [])
    failed = result.get("failed", {})
    logger.info(
        "repo sync done: %d cloned, %d updated, %d failed",
        len(cloned),
        len(pulled),
        len(failed),
    )
    if failed:
        activity_bus.publish_event(
            "sync",
            f"Repo sync failed — {len(failed)} repo(s) failed",
            detail=(
                f"{len(cloned)} cloned, {len(pulled)} updated; "
                f"{', '.join(f'{k}: {str(v)}' for k, v in failed.items())}"
            ),
            data={"cloned": len(cloned), "pulled": len(pulled), "failed": list(failed)},
        )
    elif not cloned and not pulled:
        activity_bus.publish_event(
            "sync",
            "Repo sync: nothing changed, nothing re-indexed",
            detail="All repos already up to date with GitHub.",
            data={"cloned": 0, "pulled": 0, "indexed": 0},
        )
    else:
        activity_bus.publish_event(
            "sync",
            f"Repo sync: {len(cloned)} cloned, {len(pulled)} updated",
            detail=(
                f"{result.get('indexed', 0)} project(s) indexed, "
                f"{result.get('knowledge', {}).get('queued', 0)} knowledge "
                "job(s) queued"
            ),
            data={
                "cloned": len(cloned),
                "pulled": len(pulled),
                "indexed": result.get("indexed", 0),
            },
        )
    return result
