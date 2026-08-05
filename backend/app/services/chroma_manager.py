"""ChromaManager — embedded ChromaDB access (docs/02 §6.1).

ChromaDB runs as an embedded python client with a persistent directory
(settings.chroma_path). One collection per knowledge source. All operations
take precomputed embeddings — no default embedding function is used, so the
model used for indexing and querying must match (nomic-embed-text).
"""

from pathlib import Path
from typing import Any

import chromadb

from app.core.config import settings

COLLECTIONS = (
    "file_summaries",
    "git_commits",
    "test_logs",
    "security_reports",
    "build_logs",
    "project_summaries",
)


class ChromaManager:
    """Owns the PersistentClient and exposes collection helpers."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or settings.chroma_path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.path))
        self._collections: dict[str, chromadb.Collection] = {}

    def collection(self, name: str) -> chromadb.Collection:
        """Get (or create) a cosine-distance collection by name."""
        cached = self._collections.get(name)
        if cached is not None:
            return cached
        collection = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        self._collections[name] = collection
        return collection

    def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        self.collection(collection).upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Similarity search; returns result dicts with metadata + distance."""
        result = self.collection(collection).query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        return [
            {
                "id": ids[i],
                "document": documents[i] if documents else None,
                "metadata": metadatas[i] if metadatas else {},
                "distance": distances[i] if distances else 1.0,
            }
            for i in range(len(ids))
        ]

    def delete_by_project(self, collection: str, project_id: str) -> None:
        """Remove all embeddings of a project from one collection."""
        self.collection(collection).delete(where={"project_id": project_id})

    def count(self, collection: str) -> int:
        return self.collection(collection).count()
