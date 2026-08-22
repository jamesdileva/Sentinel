"""BackupService — deterministic state snapshots (v1.17.18.1, audit A1).

Creates a consistent backup of Sentinel's local state: the SQLite database
(via the sqlite3 online-backup API — safe to run while the server is up,
WAL-aware), the Chroma index, session screenshots and the run logs, zipped
into `data/backups/sentinel-<UTC timestamp>.zip`. Keeps the newest N
backups and prunes the rest. User-initiated only (CLI `sentinel backup` or
`scripts/backup.py`) — never a beat (docs/01 Rule 2).
"""

import datetime
import shutil
import sqlite3
import zipfile
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def backups_dir() -> Path:
    return Path(settings.db_path).parent.parent / "backups"


def _zip_path(stamp: datetime.datetime) -> Path:
    return backups_dir() / f"sentinel-{stamp:%Y%m%d-%H%M%S}.zip"


def _snapshot_db(dest: Path) -> None:
    """Consistent SQLite snapshot via the online backup API (WAL-safe:
    readers see a single consistent state even while writers are active)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(settings.db_path))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _add_dir(zf: zipfile.ZipFile, src_dir: Path, arc_root: str) -> int:
    """Zip a directory tree under `arc_root`; returns the file count."""
    if not src_dir.is_dir():
        return 0
    count = 0
    for path in sorted(src_dir.rglob("*")):
        if path.is_file():
            zf.write(path, Path(arc_root) / path.relative_to(src_dir))
            count += 1
    return count


def create_backup(keep: int = 7, push_dir: str | Path | None = None) -> dict:
    """Snapshot db + chroma + screenshots + logs into one zip, prune old
    backups. When `push_dir` is set, the finished zip is copied there
    (another drive / synced folder) so a dead system disk doesn't take the
    backups with it — v1.17.18.6, crash-resilience follow-up. Returns stats;
    never raises (defensive — a backup failure must not crash the CLI)."""
    stamp = datetime.datetime.now(datetime.timezone.utc)
    target = _zip_path(stamp)
    backups_dir().mkdir(parents=True, exist_ok=True)
    db_snapshot = backups_dir() / "sentinel.db.snapshot"

    stats = {"path": str(target), "files": 0, "skipped": []}
    try:
        _snapshot_db(db_snapshot)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_snapshot, "sqlite/sentinel.db")
            stats["files"] += 1
            stats["files"] += _add_dir(zf, Path(settings.chroma_path), "chroma")
            stats["files"] += _add_dir(
                zf,
                backups_dir().parent.parent / "screenshots",
                "screenshots",
            )
            stats["files"] += _add_dir(zf, backups_dir().parent / "logs", "logs")
    except Exception:  # noqa: BLE001 — report the failure, never crash
        logger.exception("Backup failed")
        stats["skipped"].append("backup failed")
        return stats
    finally:
        db_snapshot.unlink(missing_ok=True)

    pruned = prune_backups(keep)
    stats["pruned"] = pruned

    # v1.17.18.6 (crash-resilience): copy the finished zip off-disk. A copy
    # failure is reported but never fails the backup itself.
    stats["pushed_to"] = None
    if push_dir:
        try:
            push_path = Path(push_dir)
            push_path.mkdir(parents=True, exist_ok=True)
            dest = push_path / target.name
            shutil.copy2(target, dest)
            stats["pushed_to"] = str(dest)
            logger.info("Backup pushed to %s", dest)
        except OSError:
            logger.exception("Backup push to %s failed", push_dir)
            stats["skipped"].append(f"push to {push_dir} failed")

    logger.info(
        "Backup created: %s (%d files); pruned %d old backup(s)",
        target.name,
        stats["files"],
        pruned,
    )
    return stats


def prune_backups(keep: int) -> int:
    """Delete all but the newest `keep` backups; returns the count removed."""
    backups = sorted(backups_dir().glob("sentinel-*.zip"))
    removed = 0
    for old in backups[:-keep] if keep > 0 else backups:
        try:
            old.unlink()
            removed += 1
        except OSError:
            logger.warning("Could not remove old backup %s", old)
    return removed


def list_backups() -> list[dict]:
    return [
        {"path": p.name, "size": p.stat().st_size, "modified": p.stat().st_mtime}
        for p in sorted(backups_dir().glob("sentinel-*.zip"))
    ]


if __name__ == "__main__":  # pragma: no cover — CLI entry (scripts/backup.py)
    result = create_backup()
    print(f"Backup written to {result['path']} ({result['files']} files)")
    if result["skipped"]:
        raise SystemExit(1)
