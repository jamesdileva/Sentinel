"""Sprint 8: RAG API endpoint tests with a fake dependency service."""

import hashlib
import math

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.v1.rag import get_rag_service
from app.db.connection import get_engine
from app.main import app
from app.services.chroma_manager import ChromaManager
from app.services.indexer import IndexerService
from app.services.rag_service import RagService
from app.tasks.rag_tasks import run_index_knowledge


def _fake_embedder(text: str) -> list[float]:
    vector = [0.0] * 64
    for token in text.lower().split():
        idx = int.from_bytes(hashlib.md5(token.encode()).digest()[:4], "little") % 64
        vector[idx] = 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _fake_llm(prompt: str) -> str:
    return "Grounded answer about the FastAPI service."


def _build_fake_rag(tmp_path) -> RagService:
    return RagService(
        session=Session(get_engine()),
        embedder=_fake_embedder,
        llm=_fake_llm,
        chroma=ChromaManager(path=tmp_path / "chroma"),
    )


def _seed(tmp_db) -> str:
    with Session(get_engine()) as session:
        return (
            IndexerService(session)
            .index_project("tests/fixtures/sample_python_project")
            .id
        )


@pytest.fixture()
def indexed(tmp_db, tmp_path):
    project_id = _seed(tmp_db)
    with Session(get_engine()) as session:
        project = RagService.get_project(session, project_id)
        _build_fake_rag(tmp_path).index_project(project)
    app.dependency_overrides[get_rag_service] = lambda: _build_fake_rag(tmp_path)
    yield project_id
    app.dependency_overrides.pop(get_rag_service, None)


@pytest.fixture()
def overridden(tmp_db, tmp_path):
    app.dependency_overrides[get_rag_service] = lambda: _build_fake_rag(tmp_path)
    yield
    app.dependency_overrides.pop(get_rag_service, None)


def test_rag_search_endpoint(indexed):
    client = TestClient(app)
    resp = client.post(
        "/api/v1/rag/search",
        json={"query": "fastapi", "project_id": indexed, "top_k": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "fastapi"
    assert len(body["results"]) >= 1
    assert body["results"][0]["source"] in {"file_summaries", "git_commits"}


def test_rag_search_preserves_provenance(indexed):
    client = TestClient(app)
    resp = client.post(
        "/api/v1/rag/search", json={"query": "fastapi", "project_id": indexed}
    )
    results = resp.json()["results"]
    assert all("distance" in r for r in results)
    assert all("file_path" in r for r in results)


def test_rag_query_endpoint(indexed):
    client = TestClient(app)
    resp = client.post(
        "/api/v1/rag/query",
        json={"question": "what does it do?", "project_id": indexed},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Grounded answer about the FastAPI service."
    assert body["model"]
    assert body["generated_at"]
    assert body["confidence"] >= 0.0
    assert len(body["sources"]) >= 1


def test_rag_search_empty_when_no_index(overridden):
    client = TestClient(app)
    resp = client.post("/api/v1/rag/search", json={"query": "nothing here"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_rag_query_no_index_helpful_answer(overridden):
    client = TestClient(app)
    resp = client.post("/api/v1/rag/query", json={"question": "anything"})
    assert resp.status_code == 200
    assert "no matching knowledge" in resp.json()["answer"].lower()
    assert resp.json()["confidence"] == 0.0


def test_rag_index_returns_job_envelope(tmp_db, monkeypatch):
    project_id = _seed(tmp_db)
    captured = {}

    def fake_submit(name, args=None, task_id=None):
        captured["name"] = name
        captured["args"] = args
        captured["task_id"] = task_id
        return "job-123"

    monkeypatch.setattr("app.api.v1.rag.job_scheduler.submit", fake_submit)
    client = TestClient(app)
    resp = client.post(
        "/api/v1/rag/index", json={"project_id": project_id, "with_summary": False}
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["job_id"] == "job-123"
    assert captured["name"] == "run_index_knowledge"
    assert captured["args"] == [project_id, False]
    assert captured["task_id"] is None


def test_rag_index_unknown_project_404(tmp_db):
    client = TestClient(app)
    resp = client.post("/api/v1/rag/index", json={"project_id": "nope"})
    assert resp.status_code == 404


def test_rag_index_status_counts(tmp_db):
    """Sprint 15: index/status reports embedded vs total files; project_id
    narrows the result set."""
    project_id = _seed(tmp_db)
    client = TestClient(app)
    resp = client.get("/api/v1/rag/index/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] is None
    entry = body["projects"][project_id]
    assert entry["files"] > 0
    assert entry["embedded"] == 0  # never embedded in this fixture
    assert body["files_total"] == entry["files"]
    assert body["files_embedded"] == 0

    scoped = client.get(
        "/api/v1/rag/index/status", params={"project_id": project_id}
    ).json()
    assert scoped["project_id"] == project_id
    assert list(scoped["projects"].keys()) == [project_id]
    assert scoped["files_total"] == body["files_total"]


def test_list_summaries_empty(tmp_db):
    project_id = _seed(tmp_db)
    client = TestClient(app)
    resp = client.get(f"/api/v1/projects/{project_id}/summaries")
    assert resp.status_code == 200
    assert resp.json() == []


def test_rag_search_unknown_project_empty(overridden):
    client = TestClient(app)
    resp = client.post(
        "/api/v1/rag/search", json={"query": "foo", "project_id": "does-not-exist"}
    )
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_list_summaries_unknown_project_404(tmp_db):
    client = TestClient(app)
    resp = client.get("/api/v1/projects/does-not-exist/summaries")
    assert resp.status_code == 404
