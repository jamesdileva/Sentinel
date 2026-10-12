"""Audit B3 (portfolio score invalidation) and B9 (settings provenance +
probe cache) — the Batch 4 items that touch how the UI is told the truth.

B3: reads stay lazy, but a row cached under an *older* component definition
has evidence timestamps that never move — only an explicit refresh heals it.
B9: a value from the process environment and one from `.env` both used to
report "env", which hides that the process environment wins.
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.db.connection import get_engine
from app.db.models import AppSession, Project, SessionStatus
from app.main import app
from app.services import settings_service
from app.services.portfolio_service import PortfolioService


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """Patch BOTH data paths: the lifespan's knowledge-pairing check compares
    settings.db_path against settings.chroma_path, and a test database
    pointed at the real store would report every vector as an orphan — as
    well as churning the real on-disk index from a hermetic test."""
    monkeypatch.setattr(settings, "chroma_path", tmp_path / "chroma")


# --- B3: portfolio score invalidation --------------------------------------


def _project(tmp_db, name="b3") -> str:
    with Session(get_engine()) as session:
        project = Project(name=name, path="/tmp/b3", language="Python")
        session.add(project)
        session.commit()
        session.refresh(project)
        return project.id


def test_read_serves_the_cached_row_without_recomputing(tmp_db, monkeypatch):
    """The audit's architecture: recompute when evidence changes, persist,
    serve the cache. A second read must not recompute anything."""
    project_id = _project(tmp_db)
    with Session(get_engine()) as session:
        service = PortfolioService(session)
        service.compute_portfolio_score(session.get(Project, project_id))
        calls = {"n": 0}
        original = service.compute_portfolio_score

        def counting(project):
            calls["n"] += 1
            return original(project)

        monkeypatch.setattr(service, "compute_portfolio_score", counting)
        rows = service.scores()
        assert len(rows) == 1
        assert calls["n"] == 0, "an unchanged score was recomputed on read"


def test_new_evidence_invalidates_the_cache(tmp_db, monkeypatch):
    """A source row newer than the stored score makes the next read
    recompute — the half of the audit's architecture that already worked."""
    project_id = _project(tmp_db)
    with Session(get_engine()) as session:
        service = PortfolioService(session)
        project = session.get(Project, project_id)
        service.compute_portfolio_score(project)

        calls = {"n": 0}
        original = service.compute_portfolio_score

        def counting(project_arg):
            calls["n"] += 1
            return original(project_arg)

        monkeypatch.setattr(service, "compute_portfolio_score", counting)
        service.scores()
        assert calls["n"] == 0, "nothing changed, yet a score was recomputed"

        # Newer evidence: a passing tester session is a score source.
        tomorrow = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            days=1
        )
        session.add(
            AppSession(
                project_id=project_id,
                title="Tester: smoke",
                status=SessionStatus.PASSED,
                ended_at=tomorrow.replace(tzinfo=None),
            )
        )
        session.commit()
        service.scores()
        assert calls["n"] == 1, "newer evidence did not invalidate the cache"


def test_refresh_forces_a_recompute(tmp_db, monkeypatch):
    """Explicit invalidation: a row cached under an older component
    definition never sees new evidence, so only this (or the startup sweep)
    heals it."""
    project_id = _project(tmp_db)
    with Session(get_engine()) as session:
        service = PortfolioService(session)
        project = session.get(Project, project_id)
        service.compute_portfolio_score(project)

        calls = {"n": 0}
        original = service.compute_portfolio_score

        def counting(project_arg):
            calls["n"] += 1
            return original(project_arg)

        monkeypatch.setattr(service, "compute_portfolio_score", counting)
        service.refresh(project_id)
        assert calls["n"] == 1


def test_refresh_unknown_project_is_an_error(tmp_db):
    with Session(get_engine()) as session:
        with pytest.raises(ValueError):
            PortfolioService(session).refresh("no-such-project")


def test_refresh_endpoint_recomputes(tmp_db):
    _project(tmp_db)
    with TestClient(app) as client:
        response = client.post("/api/v1/portfolio/scores/refresh")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["project_id"]
    assert "portfolio_score" in body[0]


def test_refresh_endpoint_unknown_project_is_404(tmp_db):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/portfolio/scores/refresh", params={"project_id": "nope"}
        )
    assert response.status_code == 404


# --- B9: settings provenance -----------------------------------------------


class _FakeOllama:
    def __init__(self, *a, **kw):
        pass

    def is_available(self):
        return True

    def list_models(self):
        return ["nomic-embed-text"]

    def close(self):
        pass


def _item(report_body, key):
    for group in report_body["groups"]:
        for item in group["items"]:
            if item["key"] == key:
                return item
    raise AssertionError(f"{key} not in report")


def test_source_distinguishes_env_file_from_the_process_environment(
    tmp_db, tmp_path, monkeypatch
):
    """B9: both used to report "env" — but the process environment wins at
    load, so the badge must not call them the same thing."""
    original = settings_service._probe_cache
    monkeypatch.setattr(settings_service, "OllamaService", _FakeOllama)
    monkeypatch.setattr(settings_service, "_probe_cache", dict(original))
    monkeypatch.setattr(settings_service, "BASE_DIR", tmp_path, raising=False)
    (tmp_path / ".env").write_text(
        "SENTINEL_OLLAMA_HOST=http://localhost:11434\n", encoding="utf-8"
    )
    monkeypatch.delenv("SENTINEL_OLLAMA_HOST", raising=False)
    with TestClient(app) as client:
        body = client.get("/api/v1/settings").json()
    assert _item(body, "SENTINEL_OLLAMA_HOST")["source"] == "env-file"

    monkeypatch.setenv("SENTINEL_OLLAMA_HOST", "http://localhost:11434")
    with TestClient(app) as client:
        body = client.get("/api/v1/settings").json()
    # Process environment wins, so the label says so.
    assert _item(body, "SENTINEL_OLLAMA_HOST")["source"] == "env"


def test_source_reports_default_for_untouched_settings(tmp_db, monkeypatch):
    monkeypatch.setattr(settings_service, "OllamaService", _FakeOllama)
    monkeypatch.setattr(
        settings_service, "_probe_cache", {"key": None, "at": 0.0, "result": None}
    )
    monkeypatch.delenv("SENTINEL_GIT_EXECUTABLE", raising=False)
    with TestClient(app) as client:
        body = client.get("/api/v1/settings").json()
    assert _item(body, "SENTINEL_GIT_EXECUTABLE")["source"] == "default"


def test_the_ollama_probe_is_cached(tmp_db, monkeypatch):
    """Batch 4: the probe ran on every page load. A cached report costs one
    request to Ollama, not one per reload."""
    probes = {"n": 0}

    class Counting:
        def __init__(self, *a, **kw):
            probes["n"] += 1

        def is_available(self):
            return True

        def list_models(self):
            return ["nomic-embed-text"]

        def close(self):
            pass

    monkeypatch.setattr(settings_service, "OllamaService", Counting)
    monkeypatch.setattr(
        settings_service, "_probe_cache", {"key": None, "at": 0.0, "result": None}
    )
    available, models = settings_service._probe_ollama()
    assert available is True and models == ["nomic-embed-text"]
    settings_service._probe_ollama()
    settings_service._probe_ollama()
    assert probes["n"] == 1, "the probe ran again inside its TTL"


def test_the_probe_cache_is_keyed_on_the_host(tmp_db, monkeypatch):
    """Changing the host must not serve the previous host's answer."""
    monkeypatch.setattr(settings_service, "OllamaService", _FakeOllama)
    monkeypatch.setattr(
        settings_service, "_probe_cache", {"key": None, "at": 0.0, "result": None}
    )
    settings_service._probe_ollama()
    monkeypatch.setattr(settings, "ollama_host", "http://127.0.0.1:11434")
    assert settings_service._probe_ollama()[0] is True
