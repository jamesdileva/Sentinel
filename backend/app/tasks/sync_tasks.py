"""Scheduled repo sync task (Sprint 12.1).

Runs `RepoSyncService.sync()` on the in-process beat schedule defined by
`SENTINEL_SYNC_INTERVAL_MINUTES`, then — since v1.17.6.6 — the daily
security scan-all as the last step: sync -> index (if needed) -> scan.
Opens its own DB session, same pattern as app/tasks/build_tasks.py.
"""

from app.core.logging import get_logger
from app.services import activity_bus
from app.services.sync_service import run_sync

logger = get_logger(__name__)


def run_repo_sync() -> dict:
    """Clone/pull GitHub repos into watch dirs, then re-index, then run the
    daily security scan-all (Rule 3 deterministic; v1.17.6.6 flow)."""
    from app.tasks.build_tasks import run_security_scan_all

    logger.info("repo sync task starting")
    result = run_sync()
    if not result.get("configured"):
        # v1.17.1: the "skipped" pill was opaque — say why on the live feed.
        activity_bus.publish_event(
            "sync",
            "Repo sync skipped — SENTINEL_GITHUB_TOKEN is not configured",
            detail="Set SENTINEL_GITHUB_TOKEN in .env and restart, or press Sync now.",
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
    # v1.17.6.6: the daily flow is sync -> index (persisted rows for the
    # background pool, above) -> security scan. The scan runs here, on the
    # beat thread, once the pull is done; queued knowledge-index jobs churn
    # in the pool meanwhile (scanning reads files on disk, never embeddings).
    try:
        scan = run_security_scan_all()
        logger.info("security scan-all after sync: %r", scan)
    except Exception:  # noqa: BLE001 — a scan failure must not fail the sync task
        logger.exception("security scan-all failed after repo sync")
    return result
