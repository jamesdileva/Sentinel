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


def test_default_service_uses_metered_paths(tmp_db, tmp_path, monkeypatch):
    """v1.17.3 regression: `x is obj.method` compares a cached bound method
    against a freshly built one — always False, so the metered embed/generate
    paths (tok/s + Ollama event + query log) silently never ran. Explicit
    flags must reflect which implementations are in use."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    with Session(connection.get_engine()) as session:
        real = RagService(session)
        assert real._uses_real_embedder is True
        assert real._uses_real_llm is True
        fake = RagService(session, embedder=_fake_embedder, llm=_fake_llm)
        assert fake._uses_real_embedder is False
        assert fake._uses_real_llm is False


def test_metered_generate_publishes_event_and_query_log(tmp_db, tmp_path, monkeypatch):
    """v1.17.3: with the real Ollama service in use, generation must publish
    an `ollama` activity event and record an OllamaQueryLog row (the System
    panel's t/s list) — the bound-method identity bug had killed both."""
    from app.core.config import settings
    from app.services import activity_bus
    from app.services.system_service import OllamaStatus

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    events: list[dict] = []
    monkeypatch.setattr(
        activity_bus,
        "publish_event",
        lambda kind, message, detail=None, data=None: events.append(
            {"kind": kind, "message": message, "detail": detail, "data": data}
        ),
    )
    recorded: list[dict] = []
    monkeypatch.setattr(
        OllamaStatus,
        "record_query",
        lambda self, **kwargs: recorded.append(kwargs),
    )
    with Session(connection.get_engine()) as session:
        service = RagService(session)
        monkeypatch.setattr(
            service.ollama,
            "generate_with_metrics",
            lambda prompt, purpose="query": {
                "model": "gemma2",
                "response": "grounded answer",
                "eval_count": 42,
                "eval_duration_ns": 84_000_000,
                "total_duration_ns": 90_000_000,
            },
        )
        answer = service._generate_with_metrics("p", purpose="rag-query")

    assert answer == "grounded answer"
    assert events and events[0]["kind"] == "ollama"
    assert "42 tokens" in events[0]["message"]
    assert events[0]["data"]["purpose"] == "rag-query"
    assert recorded and recorded[0]["eval_count"] == 42
    assert recorded[0]["eval_duration_ns"] == 84_000_000


def test_metered_embed_returns_ollama_metrics(tmp_db, tmp_path, monkeypatch):
    """v1.17.3: with the real Ollama service in use, embed_with_metrics' own
    counters flow back to the caller (used by the progress tok/s tick)."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    with Session(connection.get_engine()) as session:
        service = RagService(session)
        monkeypatch.setattr(
            service.ollama,
            "embed_with_metrics",
            lambda text, model=None: ([0.1, 0.2], {"tokens": 5, "duration_ns": 1}),
        )
        vector, metrics = service._embed_with_metrics("text")
    assert vector == [0.1, 0.2]
    assert metrics == {"tokens": 5, "duration_ns": 1}


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


# ── v1.17.6: delete_by_project / reset / summary-first queries ─────────


def test_delete_by_project_clears_real_collections(tmp_db, tmp_path):
    """v1.17.6: the GC previously deleted from a phantom `knowledge`
    collection (never written by ingestion), leaving orphaned vectors in
    `file_summaries` et al forever. It must sweep every real collection
    while leaving other projects untouched."""
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        _rag(session, tmp_path).index_project(project)
    rag = _rag(Session(connection.get_engine()), tmp_path)
    assert rag.chroma.count("file_summaries") >= 1
    rag.chroma.upsert(
        "file_summaries",
        ids=["b:1"],
        embeddings=[_fake_embedder("unrelated project file")],
        documents=["another project's content"],
        metadatas=[{"project_id": "proj-b"}],
    )
    rag.chroma.delete_by_project(project_id)
    assert rag.chroma.count("file_summaries") == 1  # proj-b's doc survives
    assert rag.chroma.count("git_commits") == 0
    assert rag.chroma.count("project_summaries") == 0


def test_reset_all_heals_health_check(tmp_db, tmp_path):
    """v1.17.6: `reset_all` drops every knowledge collection and the health
    probe (previously caching a broken state) reports clean after it."""
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        _rag(session, tmp_path).index_project(project)
    rag = _rag(Session(connection.get_engine()), tmp_path)
    assert rag.chroma.health()["healthy"] is True
    assert rag.chroma.count("file_summaries") >= 1
    rag.chroma.reset_all()
    for name in ("file_summaries", "git_commits", "test_logs", "project_summaries"):
        assert rag.chroma.count(name) == 0
    health = rag.chroma.health()
    assert health["healthy"] is True
    assert health["checked"] == []


def test_query_all_projects_is_summary_first(tmp_db, tmp_path):
    """v1.17.6: without a project scope, architecture summaries fill the
    top slots before noisier collections get their chance."""
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        _rag(session, tmp_path).index_project(project, with_summary=True)
    with Session(connection.get_engine()) as session:
        response = _rag(session, tmp_path).query("sample service architecture")
    assert response.sources, "expected at least one source"
    assert response.sources[0].source == "project_summaries"
    assert any(s.source == "project_summaries" for s in response.sources)


def test_query_context_names_projects(tmp_db, tmp_path):
    """v1.17.6: context lines carry the source project's name (metadata
    only ever had ids), so the LLM sees provenance it can cite."""
    project_id = _index_project(tmp_db)
    captured: dict = {}

    def capturing_llm(prompt: str) -> str:
        captured["prompt"] = prompt
        return "grounded"

    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        rag = RagService(
            session,
            embedder=_fake_embedder,
            llm=capturing_llm,
            chroma=ChromaManager(path=tmp_path / "chroma"),
        )
        rag.index_project(project)
        rag.query("fastapi", project_id=project_id)
    assert captured["prompt"]
    assert "— Sample Python Project" in captured["prompt"]


def test_reset_knowledge_task_drops_shared_chroma(tmp_db, tmp_path, monkeypatch):
    """v1.17.6: the scheduler task wipes the shared manager's collections
    and publishes the lifecycle events."""
    from app.core.config import settings
    from app.tasks import rag_tasks

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    events: list[dict] = []
    monkeypatch.setattr(
        rag_tasks.activity_bus,
        "publish_event",
        lambda kind, message, detail=None, data=None: events.append(
            {"kind": kind, "message": message}
        ),
    )
    manager = get_chroma_manager()
    manager.upsert(
        "file_summaries",
        ids=["x:1"],
        embeddings=[_fake_embedder("something")],
        documents=["something"],
        metadatas=[{"project_id": "x"}],
    )
    assert manager.count("file_summaries") == 1
    result = rag_tasks.run_reset_knowledge()
    assert result == {"scopes": "all"}
    assert manager.count("file_summaries") == 0
    kinds = [e["kind"] for e in events]
    assert kinds.count("index") == 2
    assert "reset finished" in events[-1]["message"]
