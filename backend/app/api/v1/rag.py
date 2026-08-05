"""RAG endpoints — /api/v1/rag (docs/02 §2.3).

Semantic search and grounded Q&A over indexed project knowledge. Queries run
in the API process (Ollama is local); indexing runs as an async Celery job.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.connection import get_session
from app.repositories import KnowledgeSummaryRepository, ProjectRepository
from app.schemas import (
    JobEnvelope,
    KnowledgeSummaryRead,
    RagIndexRequest,
    RagQueryRequest,
    RagResponse,
    RagSearchRequest,
    RagSearchResponse,
)
from app.services.rag_service import RagService
from app.tasks.rag_tasks import run_index_knowledge

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
    job_id = str(uuid.uuid4())
    run_index_knowledge.apply_async(
        args=[project.id, payload.with_summary], task_id=job_id
    )
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
