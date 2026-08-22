"""Sprint 8: RagService tests — fake embedder/LLM, real ChromaDB at tmp_path."""

from chromadb.errors import InternalError
from sqlmodel import Session

from app.db import connection
from app.services.chroma_manager import COLLECTIONS, ChromaManager, get_chroma_manager
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
    caps: list[int] = []
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
            lambda prompt, purpose="query", max_tokens=500: caps.append(max_tokens)
            or {
                "model": "gemma2",
                "response": "grounded answer",
                "eval_count": 42,
                "eval_duration_ns": 84_000_000,
                "total_duration_ns": 90_000_000,
            },
        )
        answer = service._generate_with_metrics("p", purpose="rag-query")

    assert answer == "grounded answer"
    assert caps == [500]  # chat answers keep the shared 500-token cap
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


def test_diversify_caps_chunks_per_file():
    """v1.17.18.6 (audit2 RAG pass): a chunked doc placing 4 pieces of the
    same file into top-K is trimmed to 2 per file (nearest-first), so the
    remaining slots surface diverse evidence. Pathless hits (summaries,
    commits) are exempt."""
    from app.services.rag_service import RagResult, _diversify

    def result(distance, file_path):
        return RagResult(
            content=f"chunk at {distance}",
            source="file_summaries",
            project_id="p1",
            file_path=file_path,
            distance=distance,
        )

    sources = [
        result(0.10, "README.md"),
        result(0.11, "README.md"),
        result(0.12, None),  # summary — exempt
        result(0.13, "README.md"),  # third chunk of same file -> dropped
        result(0.14, "src/app.py"),
        result(0.15, "src/app.py"),
        result(0.16, "docs/guide.md"),
    ]
    kept = _diversify(sources)
    paths = [r.file_path or "" for r in kept]
    assert paths.count("README.md") == 2
    assert paths.count("") == 1
    assert kept[-1].file_path == "docs/guide.md"  # diversity reached slot 5


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


def test_overview_question_answered_from_stored_summary(tmp_db, tmp_path):
    """v1.17.13: a project-scoped overview question returns the stored
    architecture summary directly — provenance preserved, preamble
    stripped, no embedding/retrieval/generation (Rule 3)."""
    import datetime

    from app.db.models import KnowledgeSummary

    project_id = _index_project(tmp_db)
    generated = datetime.datetime.now()
    with Session(connection.get_engine()) as session:
        session.add(
            KnowledgeSummary(
                project_id=project_id,
                type="architecture",
                content=(
                    "Here is a concise architecture summary of the sample:\n\n"
                    "**Overview**\nSample is a FastAPI service."
                ),
                model="llama3.1:8b",
                generated_at=generated,
            )
        )
        session.commit()
    with Session(connection.get_engine()) as session:
        response = _rag(session, tmp_path).query(
            "what is this project about?", project_id=project_id
        )

    assert response.answer == "**Overview**\nSample is a FastAPI service."
    assert response.sources[0].source == "project_summaries"
    assert response.sources[0].project_id == project_id
    assert response.sources[0].distance == 0.0
    assert response.model == "llama3.1:8b"
    assert response.generated_at == generated
    assert response.confidence == 1.0


def test_overview_question_falls_through_without_summary(tmp_db, tmp_path):
    """v1.17.13: no stored summary → the overview question takes the normal
    pipeline (here: the helpful no-knowledge answer), never a silent miss."""
    with Session(connection.get_engine()) as session:
        response = _rag(session, tmp_path).query(
            "what is this project about?", project_id="p-missing"
        )
    assert "no matching knowledge" in response.answer.lower()


def test_is_overview_question_gate():
    """v1.17.13: the deterministic intent gate admits short overview
    questions and lets specific how/where/why/detail questions through."""
    from app.services.rag_service import _is_overview_question

    assert _is_overview_question("what is this project about?")
    assert _is_overview_question("What does this project do?")
    assert _is_overview_question("tell me about this project")
    assert _is_overview_question("summarize this project for me")
    assert _is_overview_question("give me an overview")
    assert not _is_overview_question("how do I build this project?")
    assert not _is_overview_question("where is the config file?")
    assert not _is_overview_question("what is this project's database schema")
    assert not _is_overview_question("what does the build pipeline run?")
    assert not _is_overview_question("what is this project about? how do I run it?")
    assert not _is_overview_question("")
    assert not _is_overview_question("x" * 121)


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
    """v1.17.6: without a project scope, architecture summaries are consulted
    before the noisier collections. v1.17.6.6: the combined hits are then
    ranked by true distance, so the closest chunk (summary OR doc) surfaces
    first — honest nearest-first ordering instead of collection priority."""
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        _rag(session, tmp_path).index_project(project, with_summary=True)
    with Session(connection.get_engine()) as session:
        response = _rag(session, tmp_path).query("sample service architecture")
    assert response.sources, "expected at least one source"
    assert any(s.source == "project_summaries" for s in response.sources)
    distances = [s.distance for s in response.sources]
    assert distances == sorted(distances)  # nearest first, no collection bias
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
    assert result == {"scopes": "all", "files_unflagged": 0}
    assert manager.count("file_summaries") == 0
    kinds = [e["kind"] for e in events]
    assert kinds.count("index") == 2
    assert "reset finished" in events[-1]["message"]


def test_reset_knowledge_task_clears_embedding_ids(tmp_db, tmp_path, monkeypatch):
    """v1.17.6.1: reset also clears ProjectFile.embedding_id — ingest_files
    skips files that look embedded, so a reset that kept the flags would
    re-embed nothing and leave the index empty forever."""
    from sqlmodel import select

    from app.core.config import settings
    from app.db.models import ProjectFile
    from app.tasks import rag_tasks

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        _rag(session, tmp_path).index_project(project)
    with Session(connection.get_engine()) as session:
        files = session.exec(
            select(ProjectFile).where(ProjectFile.project_id == project_id)
        ).all()
        assert files and all(f.embedding_id for f in files)
    result = rag_tasks.run_reset_knowledge()
    assert result["files_unflagged"] >= 1
    with Session(connection.get_engine()) as session:
        files = session.exec(
            select(ProjectFile).where(ProjectFile.project_id == project_id)
        ).all()
        assert files and all(f.embedding_id is None for f in files)


def test_reset_knowledge_cancels_queued_index_jobs(tmp_db, tmp_path, monkeypatch):
    """v1.17.7.2: a reset must cancel queued re-index jobs before clearing
    the flags — otherwise the pool re-embeds seconds later and the reset
    looks like a no-op (the boot auto-index queues ~20 projects)."""
    from app.core.config import settings
    from app.services import job_scheduler
    from app.tasks import rag_tasks

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    calls: list[str] = []
    monkeypatch.setattr(
        job_scheduler.scheduler,
        "cancel_queued",
        lambda prefix: calls.append(prefix) or 3,
    )
    result = rag_tasks.run_reset_knowledge()
    assert calls == ["run_index_knowledge"]
    assert result["files_unflagged"] == 0


def test_run_index_knowledge_all_skips_embedded_and_backfills_summaries(
    tmp_db, tmp_path, monkeypatch
):
    """v1.17.6.4: the re-index-all pass is incremental — files with an
    embedding_id are skipped (no re-embedding), while a missing architecture
    summary (post-reset, or a v1.17.6.3 timed-out generation) is
    regenerated."""
    from sqlmodel import select

    from app.core.config import settings
    from app.db.models import KnowledgeSummary
    from app.services.chroma_manager import get_chroma_manager
    from app.tasks import rag_tasks

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        service = RagService(
            session,
            embedder=_fake_embedder,
            llm=_fake_llm,
            chroma=get_chroma_manager(),
        )
        counts = service.index_project(project, with_summary=True)
        assert counts["file_summaries"] >= 1
        files_before = get_chroma_manager().count("file_summaries")
        service.chroma.reset("project_summaries")

    class FakeRag(rag_tasks.RagService):
        def __init__(self, session):
            super().__init__(session, embedder=_fake_embedder, llm=_fake_llm)

    monkeypatch.setattr(rag_tasks, "RagService", FakeRag)
    result = rag_tasks.run_index_knowledge_all()

    assert result == {"projects": 1, "ok": 1, "failed": 0}
    assert get_chroma_manager().count("project_summaries") == 1
    assert get_chroma_manager().count("file_summaries") == files_before
    with Session(connection.get_engine()) as session:
        rows = session.exec(
            select(KnowledgeSummary).where(KnowledgeSummary.project_id == project_id)
        ).all()
        assert len(rows) == 1  # the regenerated summary, not a duplicate


def test_run_index_knowledge_all_survives_one_bad_project(
    tmp_db, tmp_path, monkeypatch
):
    """v1.17.6.4: a single project whose re-index raises must not abort the
    pass — the remaining projects still complete (deterministic runbook)."""
    from app.core.config import settings
    from app.db.models import Project
    from app.tasks import rag_tasks

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        session.add(
            Project(
                name="Kaboom",
                path=str(tmp_path / "kaboom"),
                language="python",
            )
        )
        session.commit()

    class FakeRag(rag_tasks.RagService):
        def __init__(self, session):
            super().__init__(session, embedder=_fake_embedder, llm=_fake_llm)

        def index_project(self, project, **kwargs):
            if project.name == "Kaboom":
                raise RuntimeError("boom")
            return {"file_summaries": 0}

    monkeypatch.setattr(rag_tasks, "RagService", FakeRag)
    result = rag_tasks.run_index_knowledge_all()

    assert result == {"projects": 2, "ok": 1, "failed": 1}


# ── v1.17.6.2: query-based health probe / summary dedupe ────────────────


class _BrokenQueryCollection:
    """get() succeeds but query() hits the damaged HNSW reader — the exact
    v1.17.6.2 laptop failure the old `get(limit=1)` probe could not see."""

    def count(self):
        return 1

    def get(self, limit=1, include=None):
        return {"embeddings": [[0.1] * 64], "ids": ["a"]}

    def query(self, query_embeddings=None, n_results=None, where=None):
        raise InternalError("Error creating hnsw segment reader: Nothing found on disk")


class _HealthyCollection(_BrokenQueryCollection):
    def query(self, query_embeddings=None, n_results=None, where=None):
        return {"ids": [["a"]], "distances": [[0.1]], "documents": [["doc"]]}


class _FakeClient:
    def __init__(self, collection):
        self._collection = collection
        self.dropped: list[str] = []

    def get_or_create_collection(self, name, metadata=None):
        return self._collection

    def delete_collection(self, name):
        self.dropped.append(name)
        raise InternalError("Error creating hnsw segment reader")


def _manager_with(client) -> ChromaManager:
    import threading

    manager = object.__new__(ChromaManager)
    manager.path = "fake"
    manager._client = client
    manager._collections = {}
    manager._locks = {}
    manager._health_cache = None
    manager._health_lock = threading.Lock()
    return manager


def test_health_probe_detects_broken_query_path():
    """v1.17.6.2: the old probe (`get(limit=1)`) could pass while the query
    path failed, leaving the dashboard healthy and the next chat query
    503ing. The probe now runs a real query with a stored embedding."""
    manager = _manager_with(_FakeClient(_BrokenQueryCollection()))
    health = manager.health()
    assert health["healthy"] is False
    assert set(health["broken"]) == set(COLLECTIONS)
    assert len(health["checked"]) == len(COLLECTIONS)


def test_health_probe_healthy_when_query_succeeds():
    manager = _manager_with(_FakeClient(_HealthyCollection()))
    health = manager.health()
    assert health["healthy"] is True
    assert health["broken"] == []


def test_reset_tolerates_internal_error_from_damaged_store():
    """v1.17.6.2: dropping a collection whose HNSW files are gone can raise
    InternalError — the collection is being discarded anyway, so that must
    count as a successful reset instead of a traceback."""
    client = _FakeClient(_BrokenQueryCollection())
    manager = _manager_with(client)
    manager.reset("file_summaries")
    assert client.dropped == ["file_summaries"]
    assert manager._health_cache is None  # invalidated for the next probe


def test_summary_generated_once_per_project(tmp_db, tmp_path):
    """v1.17.6.2: auto-indexing always requests summaries, so the second
    index of a project must not burn a fresh Ollama generation — an
    existing architecture summary is reused unless force=True (CLI
    `--summary`). v1.17.6.3: regeneration reuses the SQLite row."""
    from sqlmodel import select

    from app.db.models import KnowledgeSummary

    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        rag = _rag(session, tmp_path)
        first = rag.index_project(project, with_summary=True)
        second = rag.index_project(project, with_summary=True)
        forced = rag.index_project(project, with_summary=True, force_summary=True)
    with Session(connection.get_engine()) as session:
        rows = session.exec(
            select(KnowledgeSummary).where(KnowledgeSummary.project_id == project_id)
        ).all()
    assert first["project_summaries"] == 1
    assert second["project_summaries"] == 0  # deduped — no new generation
    assert forced["project_summaries"] == 1  # explicit force regenerates
    assert len(rows) == 1  # regeneration reuses the row (v1.17.6.3)


def test_summary_regenerated_after_reset(tmp_db, tmp_path):
    """v1.17.6.3: the dedupe must check the embedding, not the row. Reset
    drops the `project_summaries` collection but keeps the SQLite rows, so a
    post-reset re-index would otherwise skip the summary forever and leave
    the collection empty (all-project chat loses its summary-first answers)."""
    from sqlmodel import select

    from app.db.models import KnowledgeSummary

    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        rag = _rag(session, tmp_path)
        first = rag.index_project(project, with_summary=True)
        rag.chroma.reset("project_summaries")  # simulate knowledge reset
        reindex = rag.index_project(project, with_summary=True)
    with Session(connection.get_engine()) as session:
        rows = session.exec(
            select(KnowledgeSummary).where(KnowledgeSummary.project_id == project_id)
        ).all()
    assert first["project_summaries"] == 1
    assert reindex["project_summaries"] == 1  # row alone must not block rebuild
    assert len(rows) == 1  # the same row was reused, not duplicated


def test_summary_regenerates_when_file_edited(tmp_db, tmp_path):
    """v1.17.18.6.4 (audit2 follow-up): an architecture summary that predates
    a file edit is stale — the next with-summary index regenerates it (row
    reused, generated_at restamped) instead of answering from a summary of
    long-gone code. Untouched projects keep their dedupe."""
    import datetime as dt

    from sqlmodel import select

    from app.db.models import KnowledgeSummary, ProjectFile

    project_id = _index_project(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        rag = _rag(session, tmp_path)
        assert rag.index_project(project, with_summary=True)["project_summaries"] == 1
        second = rag.index_project(project, with_summary=True)
        assert second["project_summaries"] == 0  # untouched -> deduped

        # Simulate an edit: bump one file's mtime past the summary.
        summary = session.exec(
            select(KnowledgeSummary).where(
                KnowledgeSummary.project_id == project_id,
                KnowledgeSummary.type == "architecture",
            )
        ).first()
        file_row = session.exec(
            select(ProjectFile).where(ProjectFile.project_id == project_id)
        ).first()
        future_ns = int(
            (
                summary.generated_at.replace(tzinfo=dt.timezone.utc)
                + dt.timedelta(days=1)
            ).timestamp()
            * 1e9
        )
        file_row.mtime_ns = future_ns
        session.add(file_row)
        session.commit()

        third = rag.index_project(project, with_summary=True)
        assert third["project_summaries"] == 1  # stale -> regenerated

        refreshed = session.exec(
            select(KnowledgeSummary).where(
                KnowledgeSummary.project_id == project_id,
                KnowledgeSummary.type == "architecture",
            )
        ).first()
        # Reuse path restamps generated_at (v1.17.18.6.4).
        assert refreshed.generated_at.replace(tzinfo=dt.timezone.utc) > dt.datetime.now(
            dt.timezone.utc
        ) - dt.timedelta(minutes=5)


def test_summary_uses_dedicated_token_cap(tmp_db, tmp_path):
    """v1.17.6.8: architecture summaries generate with the dedicated
    `ollama_summary_max_tokens` cap (1250), not the shared 500-token
    default — the doc-first prompt feeds ~10k tokens of context and a
    structured components/stack/notes summary outgrows 500. Chat answers
    keep the 500 default."""
    from sqlmodel import select

    from app.core.config import settings
    from app.db.models import KnowledgeSummary

    project_id = _index_project(tmp_db)

    class RecordingOllama:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def generate_with_metrics(
            self,
            prompt: str,
            purpose: str = "query",
            max_tokens: int = 500,
            temperature: float = 0.3,
            model: str | None = None,
        ) -> dict:
            self.calls.append({"purpose": purpose, "max_tokens": max_tokens})
            return {
                "response": "Summary text",
                "model": model or settings.ollama_model,
                "purpose": purpose,
                "eval_count": 12,
                "eval_duration_ns": 1,
                "total_duration_ns": 1,
            }

    ollama = RecordingOllama()
    with Session(connection.get_engine()) as session:
        project = RagService.get_project(session, project_id)
        rag = RagService(
            session,
            embedder=_fake_embedder,
            chroma=ChromaManager(path=tmp_path / "chroma"),
        )  # no llm arg -> the real metrics path runs against RecordingOllama
        rag.ollama = ollama  # type: ignore[assignment]
        counts = rag.index_project(project, with_summary=True)
        rag._generate_with_metrics("question?", purpose="rag-query")
    with Session(connection.get_engine()) as session:
        rows = session.exec(
            select(KnowledgeSummary).where(KnowledgeSummary.project_id == project_id)
        ).all()
    assert counts["project_summaries"] == 1
    assert len(rows) == 1
    summary_call = next(c for c in ollama.calls if c["purpose"] == "summary")
    assert summary_call["max_tokens"] == settings.ollama_summary_max_tokens == 1250
    assert ollama.calls[-1] == {"purpose": "rag-query", "max_tokens": 500}


# ── v1.17.6.6: doc chunking / docs-first summaries / scaled all-scope ──


def _utc(year: int, month: int, day: int):
    import datetime

    return datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc)


def test_doc_files_chunked_and_code_single_chunk(tmp_db, tmp_path):
    """v1.17.6.6: Markdown documentation is embedded in overlapping chunks
    (ids `row#i`, metadata keeps `file_path`) so vectors cover the WHOLE doc
    — not just the first 4k chars; code files stay a single truncated chunk
    (source lines keep their context when cited)."""
    from sqlmodel import select

    from app.db.models import ProjectFile

    root = tmp_path / "chunky"
    root.mkdir()
    (root / "README.md").write_text(
        "HEAD-MARKER\n" + ("A" * 2400) + "\nTAIL-MARKER" + ("B" * 120),
        encoding="utf-8",
    )
    (root / "main.py").write_text("# main\n" + ("x" * 8000), encoding="utf-8")

    with Session(connection.get_engine()) as session:
        rag = _rag(session, tmp_path)
        project = IndexerService(session).index_project(str(root))
        counts = rag.index_project(project)
        assert counts["file_summaries"] == 3  # 2 README chunks + 1 code chunk

        data = rag.chroma.collection("file_summaries").get(
            include=["documents", "metadatas"]
        )
        docs_by_file: dict[str, list[str]] = {}
        for doc, meta in zip(data["documents"], data["metadatas"]):
            docs_by_file.setdefault(meta["file_path"], []).append(doc)

        readme_docs = docs_by_file["README.md"]
        assert len(readme_docs) == 2
        assert any("HEAD-MARKER" in d for d in readme_docs)
        # the tail lies beyond the first 2000 chars — only chunking finds it
        assert any("TAIL-MARKER" in d for d in readme_docs)
        assert any(meta["file_path"] == "README.md" for meta in data["metadatas"])

        code_docs = docs_by_file["main.py"]
        assert len(code_docs) == 1
        assert len(code_docs[0]) <= 4000 + len("main.py\n\n")  # truncated once

    with Session(connection.get_engine()) as session:
        files = session.exec(
            select(ProjectFile).where(ProjectFile.project_id == project.id)
        ).all()
        # the ProjectFile marker still covers the whole file (incremental skip)
        assert all(f.embedding_id == f.id for f in files)


def test_chunk_document_bounds(tmp_path):
    """v1.17.6.6: the chunker returns overlapping fixed-size chunks and
    always at least one; it stops at the per-file cap."""
    from app.services.rag_service import _DOC_CHUNK_MAX, _chunk_document

    content = "x" * 4500
    chunks = _chunk_document(content)
    assert len(chunks) == 3  # 2000/200-overlap on 4500 chars
    assert all(chunks[i].startswith("x") for i in range(3))
    assert content in "".join(chunks)  # overlap preserves every byte
    assert len(_chunk_document("tiny")) == 1
    assert len(_chunk_document("y" * (_DOC_CHUNK_MAX * 2000 + 500))) == _DOC_CHUNK_MAX


def test_summary_context_ranks_docs_first_and_appends_commits(tmp_db, tmp_path):
    """v1.17.6.6: `_file_summary_context` ranks root README > docs/ markdown
    > entry files > code (the old by-path sampling buried the docs), and
    appends recent commit messages so the summary can reflect the project's
    phase history (sprints ~ git history)."""
    from app.db.models import GitCommit, Project, ProjectFile

    root = tmp_path / "docsy"
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "README.md").write_text("README CONTENT 101", encoding="utf-8")
    (root / "docs" / "sprint-plan.md").write_text("SPRINT PLAN", encoding="utf-8")
    (root / "docs" / "implementation.md").write_text("IMPL GUIDE", encoding="utf-8")
    (root / "run.py").write_text("run entry", encoding="utf-8")
    (root / "src" / "util.py").write_text("code", encoding="utf-8")
    (root / "notes.txt").write_text("notes", encoding="utf-8")

    with Session(connection.get_engine()) as session:
        project = Project(name="docsy", path=str(root), language="python")
        session.add(project)
        session.flush()
        session.add_all(
            [
                ProjectFile(
                    project_id=project.id,
                    path="README.md",
                    absolute_path=str(root / "README.md"),
                ),
                ProjectFile(
                    project_id=project.id,
                    path="docs/sprint-plan.md",
                    absolute_path=str(root / "docs" / "sprint-plan.md"),
                ),
                ProjectFile(
                    project_id=project.id,
                    path="docs/implementation.md",
                    absolute_path=str(root / "docs" / "implementation.md"),
                ),
                ProjectFile(
                    project_id=project.id,
                    path="run.py",
                    absolute_path=str(root / "run.py"),
                ),
                ProjectFile(
                    project_id=project.id,
                    path="src/util.py",
                    absolute_path=str(root / "src" / "util.py"),
                ),
                ProjectFile(
                    project_id=project.id,
                    path="notes.txt",
                    absolute_path=str(root / "notes.txt"),
                ),
            ]
        )
        session.add_all(
            [
                GitCommit(
                    project_id=project.id,
                    hash="a1",
                    message="feat: add scraper",
                    timestamp=_utc(2026, 8, 1),
                ),
                GitCommit(
                    project_id=project.id,
                    hash="a2",
                    message="docs: sprint 3 wrap-up",
                    timestamp=_utc(2026, 8, 2),
                ),
            ]
        )
        session.commit()
        rag = _rag(session, tmp_path)
        context = rag._file_summary_context(project)

    assert context.index("README.md") < context.index("docs/sprint-plan.md")
    assert context.index("docs/sprint-plan.md") < context.index(
        "docs/implementation.md"
    )
    assert context.index("docs/implementation.md") < context.index("run.py")
    assert context.index("run.py") < context.index("src/util.py")
    assert context.index("src/util.py") < context.index(
        "notes.txt"
    )  # last: not a doc/entry file
    assert "Recent commit history (newest first):" in context
    assert "feat: add scraper" in context and "docs: sprint 3 wrap-up" in context


def test_all_scope_query_scales_top_k_with_project_count(tmp_db, tmp_path):
    """v1.17.6.6: portfolio-wide questions raise their retrieval to the
    indexed-project count (capped), so "what do these projects do?" sees one
    summary per project instead of stopping at the fixed top_k."""
    with Session(connection.get_engine()) as session:
        rag = _rag(session, tmp_path)
        root = tmp_path / "portfolio"
        for i in range(7):
            project_dir = root / f"service-{i}"
            project_dir.mkdir(parents=True)
            (project_dir / "README.md").write_text(
                f"Service {i}: pipeline worker for data processing.",
                encoding="utf-8",
            )
            project = IndexerService(session).index_project(str(project_dir))
            rag.index_project(project, with_summary=True)

    with Session(connection.get_engine()) as session:
        response = _rag(session, tmp_path).query("what do these services do?", top_k=2)

    summaries = [s for s in response.sources if s.source == "project_summaries"]
    assert len(summaries) == 7  # scaled up from the requested top_k=2
    assert len(summaries) == len({s.project_id for s in summaries})
    assert response.answer  # still generated and grounded
    assert response.confidence >= 0.0
