"""RAG endpoints — /api/v1/rag (docs/02 §2.3).

Semantic search and grounded Q&A over indexed project knowledge. Queries run
in the API process (Ollama is local); indexing runs as an in-process
scheduler job.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.db.connection import get_session
from app.db.models import ChatMessage, ProjectFile
from app.repositories import KnowledgeSummaryRepository, ProjectRepository
from app.schemas import (
    ChatMessageCreate,
    ChatMessageRead,
    JobEnvelope,
    KnowledgeSummaryRead,
    RagIndexRequest,
    RagQueryRequest,
    RagResponse,
    RagSearchRequest,
    RagSearchResponse,
)
from app.services.job_scheduler import scheduler as job_scheduler
from app.services.rag_service import RagService

router = APIRouter(tags=["rag"])


def _project_or_404(project_id: str, session: Session) -> object:
    project = ProjectRepository(session).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}")
    return project


def get_rag_service(session: Session = Depends(get_session)) -> RagService:
    """FastAPI dependency: RAG service bound to the request session."""
    return RagService(session)


@router.post("/rag/search", response_model=RagSearchResponse)
def rag_search(
    payload: RagSearchRequest,
    rag: RagService = Depends(get_rag_service),
) -> RagSearchResponse:
    """Semantic search across indexed project knowledge."""
    return RagSearchResponse(
        query=payload.query,
        results=rag.search(
            payload.query, project_id=payload.project_id, top_k=payload.top_k
        ),
    )


@router.post("/rag/query", response_model=RagResponse)
def rag_query(
    payload: RagQueryRequest,
    rag: RagService = Depends(get_rag_service),
) -> RagResponse:
    """Ask a question; answer is grounded in retrieved context with sources."""
    return rag.query(
        payload.question, project_id=payload.project_id, top_k=payload.top_k
    )


@router.post("/rag/index", status_code=202, response_model=JobEnvelope)
def rag_index(
    payload: RagIndexRequest, session: Session = Depends(get_session)
) -> JobEnvelope:
    """Enqueue knowledge ingestion for a project."""
    project = _project_or_404(payload.project_id, session)
    job_id = job_scheduler.submit(
        "run_index_knowledge", args=[project.id, payload.with_summary]
    )
    return JobEnvelope(job_id=job_id, status="queued")


@router.post("/rag/index/all", status_code=202, response_model=JobEnvelope)
def rag_index_all(session: Session = Depends(get_session)) -> JobEnvelope:
    """Re-index every project's knowledge with AI architecture summaries
    (v1.17.6.4, Knowledge-page "Re-index all projects" button).

    Fully incremental: already-embedded files are skipped, so this mostly
    backfills missing architecture summaries; projects with new or
    unembedded files (post-git-pull) embed those too. Queued as one
    deterministic job that never aborts on a single project failure."""
    job_id = job_scheduler.submit("run_index_knowledge_all")
    return JobEnvelope(job_id=job_id, status="queued")


@router.get("/rag/index/status")
def rag_index_status(
    project_id: str | None = None,
    session: Session = Depends(get_session),
    rag: RagService = Depends(get_rag_service),
) -> dict:
    """Index progress: embedded vs total files, per project or across all
    projects (Sprint 15), plus knowledge-index health (v1.17.6).

    `health` probes every non-empty collection's HNSW index on disk; a
    damaged index (killed write) lists its collections under `broken` so the
    dashboard can offer a rebuild instead of failing on the next query.
    Read-only; no job is triggered here.

    v1.17.7.3: the service comes through `Depends` like every sibling route —
    the direct `get_rag_service(session)` call silently bypassed
    `dependency_overrides`, so the hermetic suite probed the real on-disk
    Chroma and went green or red on its state instead of the fixture's."""
    stmt = (
        select(
            ProjectFile.project_id,
            func.count(ProjectFile.id),
            func.count(ProjectFile.embedding_id),
        )
        .group_by(ProjectFile.project_id)
        .order_by(ProjectFile.project_id)
    )
    if project_id:
        stmt = stmt.where(ProjectFile.project_id == project_id)
    per_project: dict[str, dict] = {}
    files_total = 0
    files_embedded = 0
    for pid, files, embedded in session.exec(stmt).all():
        per_project[str(pid)] = {"files": int(files), "embedded": int(embedded)}
        files_total += int(files)
        files_embedded += int(embedded)
    return {
        "project_id": project_id,
        "projects": per_project,
        "files_total": files_total,
        "files_embedded": files_embedded,
        "health": rag.chroma.health(),
    }


@router.post("/rag/index/reset", status_code=202, response_model=JobEnvelope)
def rag_index_reset(session: Session = Depends(get_session)) -> JobEnvelope:
    """Drop every knowledge collection so indexing can rebuild from scratch.

    Recovery path for a damaged on-disk HNSW index (v1.17.6) — the route is
    safe to call at any time; resetting only deletes derived vectors, never
    source data or rows. Queued as a job because six collections can take
    seconds to drop."""
    job_id = job_scheduler.submit("run_reset_knowledge")
    return JobEnvelope(job_id=job_id, status="queued")


@router.get(
    "/projects/{project_id}/summaries", response_model=list[KnowledgeSummaryRead]
)
def list_summaries(
    project_id: str,
    type: str | None = None,
    session: Session = Depends(get_session),
) -> list[object]:
    """AI-generated project summaries (provenance: model + generated_at)."""
    _project_or_404(project_id, session)
    return KnowledgeSummaryRepository(session).get_by_project(project_id, type)


@router.get("/rag/chat/{project_id}", response_model=list[ChatMessageRead])
def chat_history(
    project_id: str,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> list[object]:
    """Persisted chat room for a project — or the literal id `__all__` for
    the all-projects room (v1.17.6.6): the all-scope chat used to skip
    history loading entirely because the client had no project id to pass;
    `project_id` is a plain string column, so the sentinel key needs no
    schema change. Newest-last so the client renders the transcript in
    order. Cap: 500 messages per page."""
    if project_id != "__all__":
        _project_or_404(project_id, session)
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .limit(max(1, min(limit, 500)))
    )
    return session.exec(stmt).all()


@router.post("/rag/chat/{project_id}", response_model=ChatMessageRead, status_code=201)
def chat_save(
    project_id: str,
    payload: ChatMessageCreate,
    session: Session = Depends(get_session),
) -> ChatMessage:
    """Persist one exchange of the project chat room — or of the `__all__`
    all-projects room (v1.17.6.6). The client saves the question
    (`role="user"`) and the grounded answer (`role="assistant"`) exactly as
    produced by /rag/query."""
    if project_id != "__all__":
        _project_or_404(project_id, session)
    message = ChatMessage(
        project_id=project_id,
        role=payload.role,
        text=payload.text,
        sources=payload.sources,
        model=payload.model,
        confidence=payload.confidence,
        error=payload.error,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message
