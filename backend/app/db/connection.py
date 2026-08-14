"""SQLite database connection and session management.

Schema definition lives in `app.db.models`; tables are created via `init_db()`
(Sprint 2 wires it into application startup).
"""

import time
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _ensure_parent_dir(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite does not enforce foreign keys by default; enable per connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _ensure_parent_dir(settings.db_path)
        _engine = create_engine(
            f"sqlite:///{settings.db_path}",
            connect_args={"check_same_thread": False},
        )
        event.listen(_engine, "connect", _enable_foreign_keys)
        logger.info("SQLite engine created at %s", settings.db_path)
    return _engine


def _migrate_columns(engine) -> None:
    """Add columns introduced after a DB was first created.

    `create_all` cannot ALTER existing tables; existing home-server DBs miss
    newer columns (e.g. ollama_query_log.purpose from v1.17), so check and
    ALTER once at startup. New databases get everything via create_all.

    v1.17.1 fix: the original check used `has_table("ollama_query_log")`, but
    SQLAlchemy names the table `ollamaquerylog` (class name lowercased) — the
    migration never matched, so pre-v1.17 DBs kept missing `purpose` and
    /system/overview 500'd. Now both spellings are probed.

    A migration is retried (SQLite can be transiently locked while other
    writers hold the file) and failures are logged loudly — a failed extra
    column must never silently wedge a read path.
    """
    # (probe table names, column, column type) — applied in order.
    _MIGRATIONS = (
        (
            ("ollama_query_log", "ollamaquerylog"),
            "purpose",
            "VARCHAR(80) NOT NULL DEFAULT 'query'",
        ),
        (("projectfile",), "mtime_ns", "BIGINT"),  # v1.17.7.1
        (("buildlog",), "launch_command", "VARCHAR(500)"),  # v1.17.8.0
    )
    inspector = __import__("sqlalchemy").inspect(engine)
    for table_names, column, column_type in _MIGRATIONS:
        table = next((name for name in table_names if inspector.has_table(name)), None)
        if table is None:
            continue
        columns = {c["name"] for c in inspector.get_columns(table)}
        if column in columns:
            continue
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                with engine.begin() as conn:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"
                    )
                logger.info("Migrated %s: added %s column", table, column)
                break
            except Exception:  # noqa: BLE001 — one bad attempt should not kill startup
                if attempt < attempts:
                    time.sleep(1.0)
                else:
                    logger.exception(
                        "Schema migration failed after %d attempts — reads on "
                        "new columns will degrade until the DB is migrated",
                        attempts,
                    )


def init_db() -> None:
    """Create all tables defined in app.db.models, then migrate older ones."""
    from app import db  # noqa: F401  (ensure models are imported)

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _migrate_columns(engine)
    logger.info("Database initialized: %s", settings.db_path)


def get_session():
    """FastAPI dependency: yields a SQLModel session."""
    with Session(get_engine()) as session:
        yield session


def check_db() -> bool:
    """Lightweight connectivity check (no table creation)."""
    try:
        with get_engine().connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False
