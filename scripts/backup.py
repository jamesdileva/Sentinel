"""sentinel backup — standalone state snapshot (audit A1, v1.17.18.1).

Wraps BackupService.create_backup for manual use:
    .\.venv\Scripts\python.exe scripts\backup.py [--keep N]

Creates data/backups/sentinel-<timestamp>.zip (SQLite online snapshot +
chroma + screenshots + logs) and prunes backups beyond the newest N.
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
    args = parser.parse_args()
    result = create_backup(keep=args.keep)
    print(f"Backup written to {result['path']} ({result['files']} files)")
    if result["skipped"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())