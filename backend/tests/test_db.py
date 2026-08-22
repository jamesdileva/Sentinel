"""Sprint 2 acceptance tests: database initialization, schema, FK, repository base."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.db import connection
from app.db.models import Project, ProjectFile
from app.repositories import Repository

EXPECTED_TABLES = {
    "project",
    "projectfile",
    "dependency",
    "securityfinding",
    "gitcommit",
    "testresult",
    "buildlog",
    "knowledgesummary",
    "portfolioscore",
    # v1.17.18.4 (audit2 D1): the dead `worldsimstate` (superseded by the
    # isolated world DB) and `configentry` (never read/written) tables were
    # removed from the models; init_db() drops leftovers from old DBs.
}


def _table_names(db_path) -> set[str]:
    with connection.get_engine().connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).all()
    return {row[0] for row in rows}


def test_init_db_creates_file(tmp_db):
    assert tmp_db.exists()
    assert tmp_db.stat().st_size > 0


def test_all_tables_exist(tmp_db):
    assert EXPECTED_TABLES.issubset(_table_names(tmp_db))


def test_init_db_idempotent(tmp_db):
    connection.init_db()
    assert EXPECTED_TABLES.issubset(_table_names(tmp_db))


def test_migrate_columns_adds_purpose_to_old_db(tmp_db):
    """v1.17.1 regression: a DB created before v1.17 has no
    `ollamaquerylog.purpose` (SQLAlchemy's actual table name for the
    OllamaQueryLog model); `init_db()` must ALTER it in (idempotently),
    otherwise /system/overview 500s on every read — the v1.17 migration
    probed the wrong spellings and never matched."""
    with connection.get_engine().begin() as conn:
        conn.exec_driver_sql("DROP TABLE ollamaquerylog")
        conn.exec_driver_sql(
            "CREATE TABLE ollamaquerylog ("
            "id VARCHAR(32) PRIMARY KEY NOT NULL, "
            "model VARCHAR(100) NOT NULL, "
            "prompt_chars INTEGER NOT NULL DEFAULT 0, "
            "response_chars INTEGER NOT NULL DEFAULT 0, "
            "eval_count INTEGER NOT NULL DEFAULT 0, "
            "eval_duration_ns INTEGER NOT NULL DEFAULT 0, "
            "total_duration_ns INTEGER NOT NULL DEFAULT 0, "
            "created_at DATETIME NOT NULL)"
        )
        conn.exec_driver_sql(
            "INSERT INTO ollamaquerylog (id, model, created_at) "
            "VALUES ('q1', 'gemma2', '2026-08-01 00:00:00')"
        )

    connection.init_db()  # create_all skips the existing table; migrate alters

    from sqlalchemy import inspect

    columns = {
        c["name"]
        for c in inspect(connection.get_engine()).get_columns("ollamaquerylog")
    }
    assert "purpose" in columns
    with connection.get_engine().connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT purpose FROM ollamaquerylog WHERE id = 'q1'"
        ).one()
    assert row[0] == "query"

    connection.init_db()  # second run must be a no-op, not an error
    columns = {
        c["name"]
        for c in inspect(connection.get_engine()).get_columns("ollamaquerylog")
    }
    assert "purpose" in columns


def test_fk_indexes_created_on_fresh_db(tmp_db):
    """v1.17.18.3 (audit2 Q4): every FK/hot-filter column carries an index —
    SQLite does not auto-index foreign keys, and per-project lookups were
    full-table scans."""
    from sqlalchemy import inspect

    indexes = {
        ix["name"]: set(ix["column_names"])
        for ix in inspect(connection.get_engine()).get_indexes("projectfile")
    }
    assert "ix_projectfile_project_id" in indexes
    assert "project_id" in indexes["ix_projectfile_project_id"]


def test_migrate_indexes_backfills_existing_db(tmp_db):
    """v1.17.18.3 (audit2 Q4): a DB created before the index migration gets
    its hot-path indexes on the next init_db() (create_all can't add them),
    idempotently."""
    from sqlalchemy import inspect

    engine = connection.get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_projectfile_project_id")
    connection.init_db()
    names = {ix["name"] for ix in inspect(engine).get_indexes("projectfile")}
    assert "ix_projectfile_project_id" in names

    connection.init_db()  # second run must be a no-op, not an error
    names = {ix["name"] for ix in inspect(engine).get_indexes("projectfile")}
    assert "ix_projectfile_project_id" in names


def test_drop_dead_columns_unblocks_dependency_inserts(tmp_db):
    """v1.17.18.6 regression (found live 2026-08-22): a pre-cleanup DB still
    has dependency.vulnerable as NOT NULL with no default, so every model
    insert omitted it and the flush failed with IntegrityError +
    PendingRollbackError on /sessions. init_db must drop the dead columns,
    after which model inserts succeed."""
    engine = connection.get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE dependency")
        # The pre-cleanup shape: dead columns present, vulnerable NOT NULL.
        conn.exec_driver_sql(
            "CREATE TABLE dependency ("
            "id VARCHAR(32) PRIMARY KEY NOT NULL, "
            "project_id VARCHAR(32) NOT NULL, "
            "name VARCHAR(100) NOT NULL, "
            "version VARCHAR(40), "
            "latest_version VARCHAR(40), "
            "type VARCHAR(20) NOT NULL, "
            "vulnerable BOOLEAN NOT NULL, "
            "severity VARCHAR(10), "
            "created_at DATETIME NOT NULL)"
        )

    connection.init_db()

    live = {c["name"] for c in __import__("sqlalchemy").inspect(engine).get_columns("dependency")}
    assert "vulnerable" not in live
    assert "latest_version" not in live

    from sqlmodel import Session

    from app.db.models import Dependency, Project

    with Session(engine) as session:
        project = Project(name="dep-fix", path="/dep-fix", language="python")
        session.add(project)
        session.flush()
        session.add(Dependency(project_id=project.id, name="zod", version="^4"))
        session.commit()  # previously raised NOT NULL constraint failed

    assert True


def test_check_schema_drift_detects_missing_column(tmp_db):
    """v1.17.18.3 (audit2 Q5): a model column missing from the live DB is
    reported (the v1.17.1 class of silent drift), instead of degrading a
    read path into an opaque 500."""
    engine = connection.get_engine()
    assert connection.check_schema_drift(engine) == []

    with engine.begin() as conn:
        # Simulate a pre-migration DB: rebuild ollamaquerylog without purpose.
        conn.exec_driver_sql("DROP TABLE ollamaquerylog")
        conn.exec_driver_sql(
            "CREATE TABLE ollamaquerylog ("
            "id VARCHAR(32) PRIMARY KEY NOT NULL, "
            "model VARCHAR(100) NOT NULL, "
            "prompt_chars INTEGER NOT NULL DEFAULT 0, "
            "response_chars INTEGER NOT NULL DEFAULT 0, "
            "eval_count INTEGER NOT NULL DEFAULT 0, "
            "eval_duration_ns INTEGER NOT NULL DEFAULT 0, "
            "total_duration_ns INTEGER NOT NULL DEFAULT 0, "
            "created_at DATETIME NOT NULL)"
        )

    drifted = connection.check_schema_drift(engine)
    assert "ollamaquerylog.purpose" in drifted


def test_startup_check_surfaces_schema_drift(tmp_db, monkeypatch):
    """The System page shows drift as a failed 'schema' check (Rule 7:
    transparency) instead of failing to boot."""
    from app.services.startup_check import run_startup_checks

    monkeypatch.setattr(
        connection,
        "check_schema_drift",
        lambda engine=None: ["ollamaquerylog.purpose"],
    )
    checks = {c.name: c for c in run_startup_checks()}
    assert checks["schema"].ok is False
    assert "ollamaquerylog.purpose" in checks["schema"].detail


def test_foreign_keys_enforced(tmp_db):
    with Session(connection.get_engine()) as session:
        orphan = ProjectFile(
            project_id="does-not-exist",
            path="orphan.py",
            absolute_path="C:/tmp/orphan.py",
        )
        session.add(orphan)
        with pytest.raises(IntegrityError):
            session.commit()


def test_repository_crud_roundtrip(tmp_db):
    with Session(connection.get_engine()) as session:
        repo = Repository(session, Project)
        project = Project(
            name="Workflow Toolkit",
            path="C:/Projects/workflow-toolkit",
            language="python",
            framework="fastapi",
        )
        repo.add(project)
        session.commit()

        assert repo.count() == 1

        fetched = repo.get(project.id)
        assert fetched is not None
        assert fetched.name == "Workflow Toolkit"
        assert fetched.framework == "fastapi"

        fetched.health_score = 92.0
        repo.update(fetched)
        session.commit()

        again = repo.get(project.id)
        assert again.health_score == 92.0

        repo.delete(again)
        session.commit()
        assert repo.count() == 0


def test_repository_list_paginated(tmp_db):
    with Session(connection.get_engine()) as session:
        repo = Repository(session, Project)
        for i in range(5):
            repo.add(
                Project(
                    name=f"Project {i}",
                    path=f"C:/Projects/p{i}",
                    language="typescript",
                )
            )
        session.commit()

        page = repo.list(skip=1, limit=2)
        assert len(page) == 2
        assert [p.name for p in page] == ["Project 1", "Project 2"]
