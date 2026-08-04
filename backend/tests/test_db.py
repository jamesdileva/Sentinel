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
