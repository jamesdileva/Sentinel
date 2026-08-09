"""RAG tasks — knowledge ingestion (Sprint 8).

Indexing runs in the in-process scheduler's worker threads so heavy embedding
work never blocks API responses.
"""

from sqlmodel import Session

from app.core.logging import get_logger
from app.db.connection import get_engine
from app.services.rag_service import RagService

logger = get_logger(__name__)


def run_index_knowledge(project_id: str, with_summary: bool = False) -> dict:
    """Ingest all knowledge sources for a project into ChromaDB."""
    logger.info("rag index task starting for %s", project_id)
    with Session(get_engine()) as session:
        project = RagService.get_project(session, project_id)
        counts = RagService(session).index_project(project, with_summary=with_summary)
        return {"project_id": project.id, "counts": counts}
