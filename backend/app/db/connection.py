"""SQLite database connection and session management.

Schema definition lives in `app.db.models`; tables are created via `init_db()`
(Sprint 2 wires it into application startup).
"""

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
    """
    try:
        inspector = __import__("sqlalchemy").inspect(engine)
        if not inspector.has_table("ollama_query_log"):
            return
        columns = {c["name"] for c in inspector.get_columns("ollama_query_log")}
        if "purpose" not in columns:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE ollama_query_log "
                    "ADD COLUMN purpose VARCHAR(80) NOT NULL DEFAULT 'query'"
                )
            logger.info("Migrated ollama_query_log: added purpose column")
    except Exception:  # noqa: BLE001 — never block startup on a migration fault
        logger.exception("Schema migration skipped (non-fatal)")


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
