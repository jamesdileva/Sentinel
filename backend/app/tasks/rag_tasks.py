"""RAG tasks — knowledge ingestion (Sprint 8).

Indexing runs in the in-process scheduler's worker threads so heavy embedding
work never blocks API responses.
"""

from typing import Callable

from sqlmodel import Session, select

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
        try:
            counts = service.index_project(
                project, with_summary=with_summary, progress=progress(project)
            )
        finally:
            service.close()  # v1.17.18.3 (audit2 S1)
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


def run_index_knowledge_all() -> dict:
    """Re-index every project's knowledge with AI architecture summaries.

    v1.17.6.4 (Knowledge-page "Re-index all projects" button + CLI
    `rag-index --all`): fully incremental — `ingest_files` skips files whose
    `embedding_id` is set, so already-indexed projects only regenerate the
    architecture summary when its embedding is missing (v1.17.6.3 dedupe),
    while projects with new or unembedded files (post-git-pull) embed those
    too. Projects run sequentially inside the job pool so the pass is
    deterministic and one failure never aborts the rest.
    """
    logger.info("index-all task starting")
    from app.db.models import Project

    with Session(get_engine()) as session:
        projects = list(session.exec(select(Project).order_by(Project.name)).all())
    total = len(projects)
    activity_bus.publish_event(
        "index",
        f"Knowledge re-index queued for {total} project(s)",
        data={"scope": "all"},
    )
    ok = 0
    failed = 0
    for project in projects:
        try:
            with Session(get_engine()) as session:
                service = RagService(session)
                try:
                    counts = service.index_project(
                        project, with_summary=True, progress=progress(project)
                    )
                finally:
                    service.close()  # v1.17.18.3 (audit2 S1)
            detail = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
            activity_bus.publish_event(
                "index",
                f"Knowledge re-indexed {project.name}",
                detail=detail or "nothing new",
                data={"project_id": project.id, "counts": counts},
            )
            ok += 1
        except Exception:  # noqa: BLE001 — one bad project must not abort the pass
            failed += 1
            logger.exception("index-all failed for %s", project.name)
    activity_bus.publish_event(
        "index",
        f"Knowledge re-index complete ({ok} ok, {failed} failed)",
        data={"scope": "all", "ok": ok, "failed": failed},
    )
    return {"projects": total, "ok": ok, "failed": failed}


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
    # v1.17.7.2: drop queued re-index jobs first, or the pool would re-embed
    # files seconds after their flags were cleared and the reset would look
    # like a no-op (an auto-index boot queue of ~20 jobs did exactly that).
    from app.services.job_scheduler import scheduler

    cancelled = scheduler.cancel_queued("run_index_knowledge")
    if cancelled:
        logger.info("reset cancelled %d queued knowledge job(s)", cancelled)
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
