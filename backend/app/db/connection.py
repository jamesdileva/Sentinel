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
        (
            ("portfolioscore",),
            "documentation_status",
            "VARCHAR(20) NOT NULL DEFAULT 'pending'",  # v1.17.18.6
        ),
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


def _migrate_indexes(engine) -> None:
    """Create the hot-path indexes on pre-existing tables (v1.17.18.3, audit2 Q4).

    `create_all` gives fresh databases every `index=True` index, but cannot
    add them to an existing DB — and SQLite does not auto-index foreign-key
    columns, so every per-project lookup was a full table scan. Idempotent:
    `IF NOT EXISTS` plus an inspector check for differently-named indexes.
    Names must match SQLAlchemy's generated convention (ix_<table>_<column>).
    """
    _INDEXES = (
        ("projectfile", "project_id"),
        ("dependency", "project_id"),
        ("securityfinding", "project_id"),
        ("gitcommit", "project_id"),
        ("testresult", "project_id"),
        ("buildlog", "project_id"),
        ("knowledgesummary", "project_id"),
        ("chatmessage", "project_id"),
        ("appsession", "project_id"),
        ("sessioncheckpoint", "session_id"),
        ("sessionscreenshot", "session_id"),
        ("triageanalysis", "session_id"),
        ("activityevent", "created_at"),
        ("ollamaquerylog", "created_at"),
    )
    inspector = __import__("sqlalchemy").inspect(engine)
    created = 0
    for table, column in _INDEXES:
        if not inspector.has_table(table):
            continue
        existing = inspector.get_indexes(table)
        name = f"ix_{table}_{column}"
        if any(column in ix["column_names"] for ix in existing):
            continue  # covered already (by this or another index)
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ("{column}")'
                )
            created += 1
        except Exception:  # noqa: BLE001 — never wedge startup on an index
            logger.exception("Index migration failed: %s on %s", name, table)
    if created:
        logger.info("Created %d missing index(es)", created)
    _migrate_unique_project_path(engine)


def _migrate_unique_project_path(engine) -> None:
    """v1.17.18.4 (audit2 S3): enforce one Project row per checkout path.
    Best-effort — if a legacy DB somehow holds duplicate paths, creation
    fails and is logged loudly instead of blocking startup; the indexer's
    get-or-create lock still prevents new duplicates."""
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                '"ix_project_path" ON "project" ("path")'
            )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Could not create unique index on project.path — duplicate rows "
            "likely exist; dedupe manually if project lookups misbehave",
            exc_info=True,
        )


def _drop_dead_tables(engine) -> None:
    """v1.17.18.4 (audit2 D1): reclaim the tombstone tables left behind by
    removed features. `worldsimstate` was superseded by the isolated world
    DB (world_sim_models.WorldSimStateRow); `configentry` never had a
    reader or writer. Both are provably dead (grep-verified), so dropping
    them is deterministic cleanup, not data loss."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    for table in ("worldsimstate", "configentry"):
        if not inspector.has_table(table):
            continue
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(f'DROP TABLE "{table}"')
            logger.info("Dropped dead table %s", table)
        except Exception:  # noqa: BLE001 — cleanup must not wedge startup
            logger.exception("Failed to drop dead table %s", table)


# v1.17.18.6: model columns removed in the audit2 data-layer cleanup that
# still exist in live DBs. Nullable ones are inert — inserts simply omit
# them. But `dependency.vulnerable` was created NOT NULL with no default,
# so every Dependency insert on a pre-cleanup DB failed with an
# IntegrityError until the column is dropped (found live, 2026-08-22).
_DEAD_COLUMNS = (
    ("dependency", ("latest_version", "vulnerable", "severity")),
    ("gitcommit", ("added_files", "modified_files", "deleted_files", "feature_tags")),
    ("knowledgesummary", ("confidence",)),
)


def _drop_dead_columns(engine) -> None:
    """Drop removed-model columns from live databases (v1.17.18.6).

    SQLite DROP COLUMN requires the column to be unreferenced by indexes,
    constraints, triggers, or views — true for all of these."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    for table, columns in _DEAD_COLUMNS:
        if not inspector.has_table(table):
            continue
        live = {c["name"] for c in inspector.get_columns(table)}
        for column in columns:
            if column not in live:
                continue
            try:
                with engine.begin() as conn:
                    conn.exec_driver_sql(
                        f'ALTER TABLE "{table}" DROP COLUMN "{column}"'
                    )
                logger.info("Dropped dead column %s.%s", table, column)
            except Exception:  # noqa: BLE001 — cleanup must not wedge startup
                logger.exception(
                    "Failed to drop dead column %s.%s — Dependency/insert "
                    "writes may still fail until this is resolved",
                    table,
                    column,
                )


def check_schema_drift(engine=None) -> list[str]:
    """Compare the live DB schema to the model metadata (v1.17.18.3, audit2 Q5).

    `create_all` cannot add columns to existing tables, so a model field
    without a matching migration leaves old deployments silently missing
    that column (the v1.17.1 /system 500 regression). Returns the list of
    model columns absent from the database — empty means no drift.
    Surfaced on /system via the "schema" startup check.
    """
    from sqlalchemy import inspect

    engine = engine or get_engine()
    inspector = inspect(engine)
    drifted: list[str] = []
    for table in SQLModel.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue  # fresh table — create_all just made it
        live = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in live:
                drifted.append(f"{table.name}.{column.name}")
    return drifted


def init_db() -> None:
    """Create all tables defined in app.db.models, then migrate older ones."""
    from app import db  # noqa: F401  (ensure models are imported)

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _migrate_columns(engine)
    _migrate_indexes(engine)
    _drop_dead_tables(engine)
    _drop_dead_columns(engine)
    drifted = check_schema_drift(engine)
    if drifted:
        logger.error(
            "Schema drift detected — model columns missing from the database: "
            "%s. Add ALTER TABLE migrations to _MIGRATIONS in "
            "app/db/connection.py; affected reads will degrade until then.",
            ", ".join(drifted),
        )
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
