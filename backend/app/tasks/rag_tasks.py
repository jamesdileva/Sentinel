"""RAG tasks — knowledge ingestion (Sprint 8).

Indexing runs in the in-process scheduler's worker threads so heavy embedding
work never blocks API responses.
"""

from typing import Callable

from sqlmodel import Session

from app.core.logging import get_logger
from app.db.connection import get_engine
from app.services import activity_bus
from app.services.rag_service import RagService

logger = get_logger(__name__)


def run_index_knowledge(project_id: str, with_summary: bool = False) -> dict:
    """Ingest all knowledge sources for a project into ChromaDB."""
    logger.info("rag index task starting for %s", project_id)
    with Session(get_engine()) as session:
        project = RagService.get_project(session, project_id)
        activity_bus.publish_event(
            "index",
            f"Knowledge indexing started for {project.name}",
            data={"project_id": project.id},
        )
        service = RagService(session)
        counts = service.index_project(
            project, with_summary=with_summary, progress=progress(project)
        )
        total = sum(counts.values())
        activity_bus.publish_event(
            "index",
            f"Knowledge indexing finished for {project.name} "
            f"({total} chunk(s) embedded)",
            detail=", ".join(f"{k}={v}" for k, v in counts.items() if v)
            or "nothing new",
            data={"project_id": project.id, "counts": counts},
        )
        return {"project_id": project.id, "counts": counts}


def run_reset_knowledge() -> dict:
    """Drop every ChromaDB knowledge collection (v1.17.6) and clear the
    embedding flags (v1.17.6.1).

    Recovery path for a damaged on-disk HNSW index: wiping the collections
    lets re-indexing rebuild clean vectors. The flags must be cleared too —
    `ingest_files` skips any file whose `embedding_id` is set (the v1.17.1
    incremental optimization), so a reset that left them in place would
    re-embed nothing and the index would stay empty. Runs in the job pool —
    resetting six collections can take seconds on a slow disk.
    """
    from sqlmodel import update

    from app.db.models import ProjectFile
    from app.services.chroma_manager import get_chroma_manager

    logger.info("knowledge reset task starting")
    activity_bus.publish_event(
        "index", "Knowledge index reset started", data={"scope": "all"}
    )
    get_chroma_manager().reset_all()
    with Session(get_engine()) as session:
        result = session.exec(update(ProjectFile).values(embedding_id=None))
        session.commit()
        cleared = result.rowcount
    activity_bus.publish_event(
        "index",
        "Knowledge index reset finished — re-index with `sentinel rag-index`",
        data={"scope": "all"},
    )
    return {"scopes": "all", "files_unflagged": cleared}


def progress(project) -> Callable:
    """Throttled per-file progress publisher (v1.17.1): gives the live
    activity feed a running "X of Y files" figure instead of only start/finish
    events (a full re-index of 2.9k files was otherwise silent for hours).
    Progress ticks carry an aggregate tok/s from Ollama's counters (v1.17.2)."""

    def emit(done: int, total_rows: int, speed: float | None = None) -> None:
        detail = None
        if speed is not None:
            detail = f"~{speed:,.0f} tok/s"
        activity_bus.publish_event(
            "knowledge",
            f"Knowledge indexing {project.name}: {done} of {total_rows} files",
            detail=detail,
            data={
                "project_id": project.id,
                "files_done": done,
                "files_total": total_rows,
                "tokens_per_second": speed,
            },
        )

    return emit
