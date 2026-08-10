"""RagService — retrieval-augmented generation (docs/02 §3.3, §6).

Pipeline: ingest knowledge sources into ChromaDB collections → embed the query →
search → build context → Ollama generates a grounded answer.

Determinism (docs/01 §16): embedder and llm are injectable so tests use fakes;
every returned answer carries model + timestamp provenance.
"""

import datetime
from pathlib import Path
from typing import Any, Callable

from sqlmodel import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import KnowledgeSummary, Project
from app.repositories import (
    BuildLogRepository,
    GitCommitRepository,
    ProjectFileRepository,
    ProjectRepository,
    SecurityRepository,
    TestRepository,
)
from app.schemas.rag import RagResponse, RagResult
from app.services.chroma_manager import COLLECTIONS, ChromaManager
from app.services.git_history import GitHistoryService
from app.services.ollama_service import OllamaService

logger = get_logger(__name__)

_MAX_DOC_CHARS = 4000
_RECENT_LIMIT = 20

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "prompts"

Embedder = Callable[[str], list[float]]
Llm = Callable[[str], str]


def _read_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


_PROJECT_SUMMARY_TEMPLATE = _read_template("project_summary.j2")
_ANSWER_TEMPLATE = _read_template("rag_answer.j2")


def _truncate(text: str, limit: int = _MAX_DOC_CHARS) -> str:
    return (text or "")[:limit]


class RagService:
    """Indexes knowledge into ChromaDB and answers questions over it."""

    def __init__(
        self,
        session: Session,
        embedder: Embedder | None = None,
        llm: Llm | None = None,
        chroma: ChromaManager | None = None,
    ) -> None:
        self.session = session
        self.ollama = OllamaService()
        self._embedder = embedder or self.ollama.embed
        self._llm = llm or self.ollama.generate
        self.chroma = chroma or ChromaManager()

    # --- ingestion -------------------------------------------------------

    def index_project(
        self,
        project: Project,
        with_summary: bool = False,
        progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, int]:
        """Ingest every knowledge source for a project. Returns counts per collection.

        `progress(done, total)` is invoked as files are embedded so callers
        (the scheduler task) can publish throttled progress events (v1.17.1).
        """
        counts: dict[str, int] = {}
        counts["file_summaries"] = self.ingest_files(project, progress=progress)
        counts["git_commits"] = self.ingest_git_commits(project)
        counts["test_logs"] = self.ingest_test_results(project)
        counts["security_reports"] = self.ingest_security_findings(project)
        counts["build_logs"] = self.ingest_build_logs(project)
        if with_summary:
            counts["project_summaries"] = self.ingest_project_summary(project)
        logger.info(
            "RAG index for %s: %s", project.name, {k: v for k, v in counts.items() if v}
        )
        return counts

    def ingest_files(
        self,
        project: Project,
        progress: Callable[[int, int], None] | None = None,
    ) -> int:
        """Embed the first chunk of each *unembedded* file (incremental, v1.17.1).

        Files whose `embedding_id` is already set are skipped — a re-index
        only embeds new files instead of re-embedding the whole project
        (the laptop's second auto-index pass was re-doing all 2.9k files).
        `embedding_id` is committed only *after* the Chroma upsert, so a crash
        mid-run leaves untouched files unmarked and they are retried later.
        """
        files = ProjectFileRepository(self.session).get_by_project(project.id)
        total = len(files)
        pending = [record for record in files if record.embedding_id is None]
        embeds: list[list[float]] = []
        docs: list[str] = []
        metas: list[dict[str, Any]] = []
        embedded: list[object] = []
        done = total - len(pending)
        for index, record in enumerate(pending):
            content = _read_local_file(record.absolute_path)
            if not content:
                # Nothing to embed; still mark the file so the "pending
                # knowledge" query (repo sync, Sprint 12.2) doesn't re-queue
                # this project forever.
                record.embedding_id = record.id
                done += 1
                if progress:
                    progress(done, total)
                continue
            doc = f"{record.path}\n\n{_truncate(content)}"
            embeds.append(self._embed(doc))
            docs.append(doc)
            metas.append(
                {
                    "project_id": project.id,
                    "file_path": record.path,
                    "language": record.language or "",
                }
            )
            record.embedding_id = record.id
            embedded.append(record)
            done += 1
            if progress and (done % 25 == 0 or done == total):
                progress(done, total)
        if not embeds:
            self.session.commit()
            return 0
        self.chroma.upsert(
            "file_summaries",
            ids=[record.id for record in embedded],
            embeddings=embeds,
            documents=docs,
            metadatas=metas,
        )
        self.session.commit()
        return len(embeds)

    def ingest_git_commits(self, project: Project) -> int:
        """Parse git history and embed commit messages into the git_commits collection."""
        GitHistoryService(self.session).analyze_history(project)
        commits = GitCommitRepository(self.session).get_by_project(project.id)
        embeds: list[list[float]] = []
        docs: list[str] = []
        metas: list[dict[str, Any]] = []
        for commit in commits:
            doc = f"{commit.message}"
            embeds.append(self._embed(doc))
            docs.append(doc)
            timestamp = commit.timestamp.isoformat() if commit.timestamp else ""
            metas.append(
                {
                    "project_id": project.id,
                    "commit_hash": commit.hash,
                    "author": commit.author or "",
                    "timestamp": timestamp,
                }
            )
        if not embeds:
            return 0
        ids = [f"{project.id}:{c.hash}" for c in commits]
        self.chroma.upsert(
            "git_commits", ids=ids, embeddings=embeds, documents=docs, metadatas=metas
        )
        return len(embeds)

    def ingest_test_results(self, project: Project) -> int:
        """Embed recent test results into the test_logs collection."""
        results = TestRepository(self.session).get_by_project(project.id, _RECENT_LIMIT)
        return self._upsert_simple(
            "test_logs",
            project,
            [
                {
                    "doc": f"{r.summary or ''}\n{_truncate(r.raw_output or '')}",
                    "meta": {"run_at": r.run_at.isoformat()},
                    "id": r.id,
                }
                for r in results
            ],
        )

    def ingest_security_findings(self, project: Project) -> int:
        findings = SecurityRepository(self.session).get_by_project(project.id)
        return self._upsert_simple(
            "security_reports",
            project,
            [
                {
                    "doc": f"[{f.severity.value}] {f.title}\n{f.description or ''}\n"
                    f"{f.file_path or ''}:{f.line_number or 0}",
                    "meta": {
                        "severity": f.severity.value,
                        "file_path": f.file_path or "",
                        "cve_id": f.cve_id or "",
                    },
                    "id": f.id,
                }
                for f in findings
            ],
        )

    def ingest_build_logs(self, project: Project) -> int:
        logs = BuildLogRepository(self.session).get_by_project(
            project.id, _RECENT_LIMIT
        )
        return self._upsert_simple(
            "build_logs",
            project,
            [
                {
                    "doc": _truncate(f"{log.stdout or ''}\n{log.stderr or ''}"),
                    "meta": {
                        "success": log.success is True,
                        "exit_code": log.exit_code if log.exit_code is not None else "",
                        "completed_at": (
                            log.completed_at.isoformat() if log.completed_at else ""
                        ),
                    },
                    "id": log.id,
                }
                for log in logs
            ],
        )

    def ingest_project_summary(self, project: Project) -> int:
        """Generate an architecture summary via Ollama, persist it, and embed it."""
        context = self._file_summary_context(project)
        prompt = _PROJECT_SUMMARY_TEMPLATE.format(
            project_name=project.name,
            language=project.language,
            framework=project.framework or "unknown",
            context=context or "No file content available.",
        )
        content = self._generate_with_metrics(prompt, purpose="summary")
        if not content:
            return 0
        summary = KnowledgeSummary(
            project_id=project.id,
            type="architecture",
            content=content,
            model=settings.ollama_model,
        )
        self.session.add(summary)
        self.session.commit()
        self.chroma.upsert(
            "project_summaries",
            ids=[summary.id],
            embeddings=[self._embed(content)],
            documents=[content],
            metadatas=[{"project_id": project.id, "summary_type": "architecture"}],
        )
        return 1

    def _file_summary_context(self, project: Project) -> str:
        files = ProjectFileRepository(self.session).get_by_project(project.id)
        blocks = []
        for record in files[:8]:
            content = _read_local_file(record.absolute_path)
            if content:
                blocks.append(f"{record.path}\n{_truncate(content, 600)}")
        return "\n\n".join(blocks)

    def _upsert_simple(
        self,
        collection: str,
        project: Project,
        items: list[dict[str, Any]],
    ) -> int:
        items = [i for i in items if i["doc"].strip()]
        if not items:
            return 0
        self.chroma.upsert(
            collection,
            ids=[i["id"] for i in items],
            embeddings=[self._embed(i["doc"]) for i in items],
            documents=[i["doc"] for i in items],
            metadatas=[{"project_id": project.id, **i["meta"]} for i in items],
        )
        return len(items)

    # --- query -----------------------------------------------------------

    def search(
        self,
        query: str,
        project_id: str | None = None,
        top_k: int = 5,
        collections: tuple[str, ...] | None = None,
    ) -> list[RagResult]:
        """Embed the query and return the top-K matching chunks across sources."""
        embedding = self._embed(query)
        names = collections or COLLECTIONS
        hits: list[tuple[float, RagResult]] = []
        where = {"project_id": project_id} if project_id else None
        for name in names:
            if self.chroma.count(name) == 0:
                continue
            for hit in self.chroma.search(name, embedding, top_k, where=where):
                meta = hit.get("metadata") or {}
                hits.append(
                    (
                        float(hit["distance"]),
                        RagResult(
                            content=hit["document"] or "",
                            source=name,
                            project_id=meta.get("project_id", ""),
                            file_path=meta.get("file_path"),
                            distance=float(hit["distance"]),
                        ),
                    )
                )
        hits.sort(key=lambda pair: pair[0])
        return [result for _, result in hits[:top_k]]

    def query(
        self,
        question: str,
        project_id: str | None = None,
        top_k: int = 5,
    ) -> RagResponse:
        """Answer a question grounded in retrieved ChromaDB context (docs/02 §6.3)."""
        sources = self.search(question, project_id=project_id, top_k=top_k)
        if not sources:
            return RagResponse(
                answer=(
                    "No matching knowledge is indexed yet for this question. "
                    "Run a RAG index (CLI: `sentinel rag-index <project>`) first."
                ),
                sources=[],
                model=settings.ollama_model,
                generated_at=datetime.datetime.now(datetime.timezone.utc),
                confidence=0.0,
            )
        context = "\n\n".join(
            f"[{i}] ({s.source}"
            + (f" — {s.file_path}" if s.file_path else "")
            + f")\n{s.content}"
            for i, s in enumerate(sources, start=1)
        )
        prompt = _ANSWER_TEMPLATE.format(context=context, question=question)
        answer = self._generate_with_metrics(prompt, purpose="rag-query")
        confidence = round(
            max(0.0, min(1.0, 1.0 - min(s.distance for s in sources))), 4
        )
        return RagResponse(
            answer=answer,
            sources=sources,
            model=settings.ollama_model,
            generated_at=datetime.datetime.now(datetime.timezone.utc),
            confidence=confidence,
        )

    # --- internals -------------------------------------------------------

    def _generate_with_metrics(self, prompt: str, purpose: str = "query") -> str:
        """Generate, record deterministic metrics, and publish an Ollama event."""
        if self._llm is not self.ollama.generate:
            return self._llm(prompt)
        try:
            result = self.ollama.generate_with_metrics(prompt, purpose=purpose)
        except Exception:  # noqa: BLE001  (fall back to the plain path)
            return self._llm(prompt)
        from app.services import activity_bus
        from app.services.system_service import OllamaStatus

        tokens = result["eval_count"]
        latency_ms = round(result["total_duration_ns"] / 1_000_000, 1)
        activity_bus.publish_event(
            "ollama",
            f"Ollama {purpose} for {tokens} tokens in {latency_ms} ms",
            detail=f"model {result['model']}",
            data={
                "model": result["model"],
                "purpose": purpose,
                "tokens": tokens,
                "eval_duration_ns": result["eval_duration_ns"],
            },
        )
        OllamaStatus(session=self.session).record_query(
            model=result["model"],
            purpose=purpose,
            prompt=prompt,
            response=result["response"],
            eval_count=result["eval_count"],
            eval_duration_ns=result["eval_duration_ns"],
            total_duration_ns=result["total_duration_ns"],
        )
        return result["response"]

    def _embed(self, text: str) -> list[float]:
        return self._embedder(text)

    @staticmethod
    def get_project(session: Session, project_id: str) -> Project:
        project = ProjectRepository(session).get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        return project


def _read_local_file(path: str | None) -> str:
    """Read a project file's text content; empty string when unreadable."""
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
