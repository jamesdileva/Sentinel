"""v1.17.7.3: one-off path-rewrite migration for the projects-root move.

The desktop's projects moved from `C:\\Users\\j` to `C:\\Users\\j\\projects`.
Moved checkouts keep their database rows — project paths, file paths and
security-finding paths are rewritten from the old root to the new one, so
the startup scan garbage-collects nothing and no history (chat, summaries,
findings, build/test results) is lost. Files are not touched; only the
absolute paths Sentinel stores are updated. A same-volume move preserves
mtime, so the indexer's fast path skips re-reading the moved trees.

Run AFTER moving the directories and BEFORE starting the server:

    backend\\.venv\\Scripts\\python.exe scripts\\migrate_projects_root.py --dry-run
    backend\\.venv\\Scripts\\python.exe scripts\\migrate_projects_root.py

The SQLite database travels with the repo (repo-root `data/`), so the script
finds it relative to this file wherever the repo now lives.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "data" / "sqlite" / "sentinel.db"

# Every table column that can hold an absolute checkout path. `project.path`
# and `projectfile.absolute_path` are full paths; `projectfile.path` is a
# relative path (kept in sync by the indexer); `securityfinding.file_path`
# is a full path when a scan produced one.
PATH_COLUMNS = [
    ("project", "path"),
    ("projectfile", "path"),
    ("projectfile", "absolute_path"),
    ("securityfinding", "file_path"),
]


def migrate(db_path: Path, old_prefix: str, new_prefix: str, dry_run: bool) -> int:
    if not db_path.exists():
        sys.exit(f"Database not found: {db_path}")
    old = old_prefix.rstrip("\\")
    new = new_prefix.rstrip("\\")
    if old == new:
        sys.exit("Old and new prefixes are identical; nothing to do.")
    conn = sqlite3.connect(db_path)
    total = 0
    try:
        for table, column in PATH_COLUMNS:
            # A row belongs to the old root when it equals it or starts with
            # `old\`. Rows already under the new prefix are excluded so the
            # migration is idempotent — a second run must not rewrite
            # `C:\Users\j\projects\...` to `C:\Users\j\projects\projects\...`.
            # GLOB is case-sensitive (SQLite LIKE is not, which would also
            # skip rows whose only difference from the new root is casing).
            where = (
                f"({column} = ? OR {column} LIKE ?) "
                f"AND {column} != ? AND {column} NOT GLOB ?"
            )
            params = (old, old + "\\%", new, new + "\\*")
            if dry_run:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {where}", params
                ).fetchone()[0]
            else:
                cursor = conn.execute(
                    f"UPDATE {table} SET {column} = ? || substr({column}, ?) "
                    f"WHERE {where}",
                    (new, len(old) + 1, *params),
                )
                count = cursor.rowcount
            if count:
                print(
                    f"{'would update' if dry_run else 'updated':13} "
                    f"{count:5d} row(s) in {table}.{column}"
                )
            total += count
        if dry_run:
            print(
                f"\n{total} row(s) would be rewritten. "
                "Re-run without --dry-run to apply."
            )
            print(
                "Reminder: run this AFTER moving the directories and BEFORE "
                "starting the server."
            )
        else:
            conn.commit()
            print(
                f"\n{total} row(s) rewritten. Restart the server to pick up "
                "the new paths."
            )
    finally:
        conn.close()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="print the row counts, write nothing"
    )
    parser.add_argument(
        "--old-prefix",
        default=r"C:\Users\j",
        help="old projects root (default: C:\\Users\\j)",
    )
    parser.add_argument(
        "--new-prefix",
        default=r"C:\Users\j\projects",
        help="new projects root (default: C:\\Users\\j\\projects)",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"database path (default: {DEFAULT_DB})",
    )
    args = parser.parse_args()
    migrate(Path(args.db), args.old_prefix, args.new_prefix, args.dry_run)


if __name__ == "__main__":
    main()
