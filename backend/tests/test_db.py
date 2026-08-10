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
    "worldsimstate",
    "configentry",
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
