"""sentinel backup — standalone state snapshot (audit A1, v1.17.18.1).

Wraps BackupService.create_backup for manual use:
    .\.venv\Scripts\python.exe scripts\backup.py [--keep N] [--push DIR]

Creates data/backups/sentinel-<timestamp>.zip (SQLite online snapshot +
chroma + screenshots + logs), prunes backups beyond the newest N, and
optionally copies the finished zip to DIR (another drive / synced folder)
so a dead system disk doesn't take the backups with it.
User-initiated only — never scheduled (docs/01 Rule 2).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.backup_service import create_backup  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Sentinel state snapshot")
    parser.add_argument("--keep", type=int, default=7, help="Backups to keep")
    parser.add_argument(
        "--push",
        metavar="DIR",
        help="Copy the finished zip to this directory (off-disk copy)",
    )
    args = parser.parse_args()
    result = create_backup(keep=args.keep, push_dir=args.push)
    print(f"Backup written to {result['path']} ({result['files']} files)")
    if result.get("pushed_to"):
        print(f"Pushed to {result['pushed_to']}")
    if result["skipped"]:
        for skipped in result["skipped"]:
            print(f"FAILED: {skipped}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())