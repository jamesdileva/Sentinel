"""System page — /api/v1/system endpoints (Sprint 12).

Read-only home-server status: Ollama availability/models/tokens-per-second
and sync status. All HTTP is mocked via httpx.MockTransport; no real servers.
"""

import httpx
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.ollama_service import OllamaService
from app.services.system_service import OllamaStatus


def _ollama_ok() -> OllamaService:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "gemma2:latest"},
                        {"name": "nomic-embed-text:latest"},
                    ]
                },
            )
        return httpx.Response(500, json={})

    return OllamaService(
        host="http://ollama:11434", transport=httpx.MockTransport(handler)
    )


def test_ollama_status_reports_live_state():
    status = OllamaStatus()
    status.ollama = _ollama_ok()
    report = status.report()
    assert report["available"] is True
    assert "gemma2:latest" in report["models"]


def test_ollama_status_records_and_reports_metrics(tmp_db):
    from sqlmodel import Session

    from app.db.connection import get_engine

    with Session(get_engine()) as session:
        status = OllamaStatus(session=session)
        status.ollama = _ollama_ok()
        status.record_query(
            model="gemma2:latest",
            prompt="what is this project about?",
            response="it is a local dev server.",
            eval_count=150,
            eval_duration_ns=1_000_000_000,
            total_duration_ns=1_100_000_000,
        )
        recent = status.recent_queries()
        assert len(recent) == 1
        assert recent[0]["tokens_per_second"] == 150.0
        assert recent[0]["latency_ms"] == 1100.0
        assert recent[0]["model"] == "gemma2:latest"


def test_system_overview_endpoint(tmp_db, monkeypatch):
    monkeypatch.setattr(OllamaStatus, "report", lambda self: {"available": True})
    with TestClient(app) as client:
        response = client.get("/api/v1/system/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["ollama"]["available"] is True
    assert "startup" in data
    assert "generated_at" in data


def test_system_ollama_endpoint(tmp_db, monkeypatch):
    monkeypatch.setattr(OllamaStatus, "report", lambda self: {"available": True})
    with TestClient(app) as client:
        response = client.get("/api/v1/system/ollama")
    assert response.status_code == 200
    assert response.json()["available"] is True


def test_system_sync_endpoint(tmp_db, monkeypatch):
    """Sprint 15: /system/sync reports the sync config and the persisted last
    run (or None) — read-only, nothing is triggered here."""
    from app.services.sync_service import persist_sync_run

    monkeypatch.setattr(settings, "auto_scan_on_startup", False)
    monkeypatch.setattr(settings, "github_token", "test-token")
    persist_sync_run(status="error", detail="HTTPStatusError: 401")
    with TestClient(app) as client:
        response = client.get("/api/v1/system/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["last_run"]["status"] == "error"
    assert body["last_run"]["detail"].startswith("HTTPStatusError")
    assert body["interval_minutes"] == settings.sync_interval_minutes


def test_system_sync_endpoint_never_synced(tmp_db, monkeypatch):
    # v1.17.1: startup spawns a background scan (which persists a skipped
    # SyncRun when no token is set) — a leftover daemon thread from an
    # earlier TestClient lazily binds the *current* engine. Disable the
    # startup pass so "never synced" stays deterministic.
    monkeypatch.setattr(settings, "auto_scan_on_startup", False)
    with TestClient(app) as client:
        response = client.get("/api/v1/system/sync")
    assert response.status_code == 200
    assert response.json()["last_run"] is None


def test_sync_now_unconfigured_returns_409(tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "github_token", "")
    with TestClient(app) as client:
        response = client.post("/api/v1/system/sync")
    assert response.status_code == 409


def test_sync_now_queues_job_and_returns_envelope(tmp_db, monkeypatch):
    """v1.17.1: the header 'Sync now' button queues the deterministic
    repo-sync job and gets a 202 envelope (like rag index)."""
    monkeypatch.setattr(settings, "github_token", "test-token")
    from app.api.v1 import system as system_api

    monkeypatch.setattr(system_api.scheduler, "submit", lambda name: "job-abc")
    with TestClient(app) as client:
        response = client.post("/api/v1/system/sync")
    assert response.status_code == 202
    assert response.json() == {"job_id": "job-abc", "status": "queued"}


def test_recent_queries_degrades_when_purpose_column_missing():
    """v1.17.1: on a pre-migration DB the purpose-column SELECT must degrade
    to an empty list — the /system page must never 500 (laptop regression)."""
    from sqlalchemy.exc import SQLAlchemyError

    from app.services.system_service import OllamaStatus

    class Broken:
        def exec(self, *args, **kwargs):
            raise SQLAlchemyError("no such column: ollamaquerylog.purpose")

    status = OllamaStatus(session=Broken())
    status.ollama = _ollama_ok()
    assert status.recent_queries() == []
    assert status.report()["recent"] == []
