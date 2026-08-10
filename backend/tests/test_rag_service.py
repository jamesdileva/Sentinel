"""Sprint 8: RagService tests — fake embedder/LLM, real ChromaDB at tmp_path."""

from sqlmodel import Session

from app.db import connection
from app.services.chroma_manager import ChromaManager, get_chroma_manager
from app.services.indexer import IndexerService
from app.services.rag_service import RagService

FI = "tests/fixtures/sample_python_project"


def test_chroma_manager_shared_per_path(tmp_path):
    """v1.17.2: concurrent PersistentClient construction races ChromaDB's
    shared-system registry — the scheduler's burst of knowledge jobs used to
    crash with `'RustBindingsAPI' object has no attribute 'bindings'`. The
    factory must hand out one client per path."""
    first = get_chroma_manager(tmp_path / "c1")
    assert get_chroma_manager(tmp_path / "c1") is first
    second = get_chroma_manager(tmp_path / "c2")
    assert second is not first
    assert get_chroma_manager(tmp_path / "c2") is second


def test_rag_service_defaults_to_shared_chroma(tmp_db, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    with Session(connection.get_engine()) as session:
        service = RagService(session, embedder=_fake_embedder, llm=_fake_llm)
        assert service.chroma is get_chroma_manager()


def test_tokens_per_second_conversion():
    from app.services.rag_service import _tokens_per_second

    assert _tokens_per_second(200, 100_000_000) == 2000.0
    assert _tokens_per_second(0, 100) is None
    assert _tokens_per_second(10, 0) is None


def test_progress_ticks_report_embed_tokens_per_second(tmp_db, tmp_path, monkeypatch):
    """v1.17.2: the ingestion progress event carries an aggregate tok/s from
    Ollama's counters so indexing shows t/s on the activity feed."""
    from app.core.config import settings
    from app.tasks import rag_tasks

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    project_id = _index_project(tmp_db)
    published: list[dict] = []
    monkeypatch.setattr(
        rag_tasks.activity_bus,
        "publish_event",
        lambda kind, message, detail=None, data=None: published.append(
            {"kind": kind, "message": message, "detail": detail, "data": data}
        ),
    )
    service = RagService(
        Session(connection.get_engine()),
        embedder=_fake_embedder,
        llm=_fake_llm,
    )
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        progress_cb = rag_tasks.progress(project)
        service.index_project(project, progress=progress_cb)
    ticks = [p for p in published if p["kind"] == "knowledge"]
    assert ticks, "knowledge ticks should have been published"
    assert all(t["data"]["tokens_per_second"] is None for t in ticks)
    assert all(t["detail"] is None for t in ticks)


def _fake_embedder(text: str) -> list[float]:
    """Deterministic bag-of-words embedding so similar texts are close."""
    import hashlib
    import math

    vector = [0.0] * 64
    for token in text.lower().split():
        digest = hashlib.md5(token.encode()).digest()
        idx = int.from_bytes(digest[:4], "little") % 64
        vector[idx] = 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _fake_llm(prompt: str) -> str:
    if "project summary" in prompt.lower() or "Summary:" in prompt:
        return "This project is a FastAPI sample service."
    return "Based on the context, this project exposes a FastAPI service."


def _index_project(tmp_db) -> str:
    with Session(connection.get_engine()) as session:
        return IndexerService(session).index_project(FI).id


def _rag(session, tmp_path) -> RagService:
    return RagService(
        session,
        embedder=_fake_embedder,
        llm=_fake_llm,
        chroma=ChromaManager(path=tmp_path / "chroma"),
    )


def test_index_project_populates_all_collections(tmp_db, tmp_path):
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        counts = _rag(session, tmp_path).index_project(project, with_summary=True)

    assert counts["file_summaries"] >= 1
    assert counts["git_commits"] >= 0
    assert counts["test_logs"] >= 0
    assert counts["security_reports"] >= 0
    assert counts["build_logs"] >= 0
    assert counts["project_summaries"] == 1


def test_search_returns_results_with_provenance(tmp_db, tmp_path):
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        rag = _rag(session, tmp_path)
        project = RagService.get_project(session, project_id)
        rag.index_project(project)

    with Session(connection.get_engine()) as session:
        results = _rag(session, tmp_path).search(
            "fastapi", project_id=project_id, top_k=5
        )

    assert results, "expected at least one search hit"
    assert all(r.project_id == project_id for r in results)
    assert all(r.source in {"file_summaries", "git_commits"} for r in results)
    assert all(0.0 <= r.distance <= 1.0 for r in results)


def test_query_returns_grounded_answer(tmp_db, tmp_path):
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        rag = _rag(session, tmp_path)
        project = RagService.get_project(session, project_id)
        rag.index_project(project)

    with Session(connection.get_engine()) as session:
        response = _rag(session, tmp_path).query(
            "what is this project?", project_id=project_id
        )

    assert response.answer.startswith("Based on the context")
    assert len(response.sources) >= 1
    assert response.sources[0].source in {"file_summaries", "git_commits"}
    assert response.model
    assert response.generated_at is not None
    assert isinstance(response.confidence, float)


def test_search_scoped_to_project_excludes_others(tmp_db, tmp_path):
    project_a = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_a)
        _rag(session, tmp_path).index_project(project)
        rag = _rag(session, tmp_path)
        # Search with a non-existent project filter returns nothing.
        scoped = rag.search("fastapi", project_id="other-project", top_k=5)
    assert scoped == []


def test_query_with_no_index_returns_helpful_message(tmp_db, tmp_path):
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        response = _rag(session, tmp_path).query("anything", project_id=project_id)
    assert "no matching knowledge" in response.answer.lower()
    assert response.confidence == 0.0


def test_index_writes_embedding_ids(tmp_db, tmp_path):
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        _rag(session, tmp_path).index_project(project)
    with Session(connection.get_engine()) as session:
        from sqlmodel import select

        from app.db.models import ProjectFile

        files = session.exec(
            select(ProjectFile).where(ProjectFile.project_id == project_id)
        ).all()
        embedded = [f for f in files if f.embedding_id]
        assert len(embedded) >= 1
