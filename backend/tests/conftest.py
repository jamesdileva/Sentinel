"""Shared pytest fixtures for backend tests."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import connection
from app.main import app


@pytest.fixture(autouse=True)
def _quiet_scheduler(monkeypatch):
    """Beats must never run during tests: dispatch stays manual (Sprint 16)."""
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    from app.services.job_scheduler import scheduler

    monkeypatch.setattr(scheduler, "run_inline", False)


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Redirect the database to a temp file and rebuild the engine."""
    monkeypatch.setattr(settings, "db_path", tmp_path / "test.db")
    _dispose_engine()
    connection.init_db()
    yield tmp_path / "test.db"
    _dispose_engine()


def _dispose_engine() -> None:
    """Close pooled SQLite connections so teardown leaks no ResourceWarnings."""
    engine = connection._engine
    connection._engine = None
    if engine is not None:
        engine.dispose()


@pytest.fixture()
def client(tmp_db):
    with TestClient(app) as c:
        yield c
