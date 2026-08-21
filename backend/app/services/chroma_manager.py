"""ChromaManager — embedded ChromaDB access (docs/02 §6.1).

ChromaDB runs as an embedded python client with a persistent directory
(settings.chroma_path). One collection per knowledge source. All operations
take precomputed embeddings — no default embedding function is used, so the
model used for indexing and querying must match (nomic-embed-text).

v1.17.6: per-collection operation locks (two knowledge jobs can no longer
interleave upserts on the same collection), a cached health probe that
detects a damaged HNSW index on disk (the `Nothing found on disk`
InternalError seen after a killed write), and `reset_all()` — the recovery
path surfaces as 503 + a rebuild hint instead of a raw 500 traceback.
"""

import logging
import threading
from pathlib import Path
from typing import Any

import chromadb
from chromadb.errors import InternalError, NotFoundError

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTIONS = (
    "file_summaries",
    "git_commits",
    "test_logs",
    "security_reports",
    "build_logs",
    "project_summaries",
)

_shared: "ChromaManager | None" = None
_shared_lock = threading.Lock()

_DAMAGED_HINT = (
    "The knowledge index is damaged on disk. Rebuild it with "
    "`sentinel rag-index --reset` (or POST /api/v1/rag/index/reset)."
)


class RagIndexError(Exception):
    """Knowledge index is damaged or unreadable (v1.17.6).

    Raised when ChromaDB cannot read its on-disk HNSW index (the low-level
    `InternalError: ... Error creating hnsw segment reader: Nothing found
    on disk` seen after a write was interrupted mid-flush). API routes map
    it to a 503 with a rebuild hint; recovery is deterministic.
    """


def get_chroma_manager(path: str | Path | None = None) -> "ChromaManager":
    """Process-wide shared PersistentClient (v1.17.2).

    ChromaDB's `SharedSystemClient` registry is keyed per path and races when
    clients are constructed concurrently — a startup burst of knowledge jobs
    (scheduler thread pool) crashed with `'RustBindingsAPI' object has no
    attribute 'bindings'` / `KeyError`. One client per path removes the race;
    callers that need a private instance (tests) still take `ChromaManager`
    directly.
    """
    global _shared
    requested = Path(path or settings.chroma_path)
    with _shared_lock:
        if _shared is None or _shared.path != requested:
            _shared = ChromaManager(requested)
        return _shared


class ChromaManager:
    """Owns the PersistentClient and exposes collection helpers."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or settings.chroma_path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.path))
        self._collections: dict[str, Any] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._health_cache: dict[str, Any] | None = None
        self._health_lock = threading.Lock()

    # -- internals ------------------------------------------------------------

    def _lock(self, name: str) -> threading.RLock:
        # RLock: `upsert`/`search`/`health` hold the collection lock while
        # calling `collection()`, which locks again — a plain Lock deadlocks
        # on every operation.
        return self._locks.setdefault(name, threading.RLock())

    @staticmethod
    def _guard(exc: Exception) -> None:
        """Translate ChromaDB's on-disk index failure into RagIndexError
        (v1.17.6): raw InternalErrors otherwise surface as 500 tracebacks
        with no recovery hint."""
        if isinstance(exc, InternalError):
            raise RagIndexError(_DAMAGED_HINT) from exc
        raise exc

    def _invalidate_health(self) -> None:
        with self._health_lock:
            self._health_cache = None

    # -- collections ----------------------------------------------------------

    def collection(self, name: str) -> Any:
        """Get (or create) a cosine-distance collection by name."""
        with self._lock(name):
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
        with self._lock(collection):
            try:
                self.collection(collection).upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )
            except Exception as exc:  # noqa: BLE001 — translate then re-raise
                self._guard(exc)
        self._invalidate_health()

    def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Similarity search; returns result dicts with metadata + distance."""
        with self._lock(collection):
            try:
                result = self.collection(collection).query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    where=where,
                )
            except Exception as exc:  # noqa: BLE001 — translate then re-raise
                self._guard(exc)
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

    def existing_ids(self, collection: str, ids: list[str]) -> set[str]:
        """Return the subset of `ids` already present in the collection.

        v1.17.18.4 (audit2 S7): lets incremental ingestion skip re-embedding
        documents whose vectors are already stored (the commit-ingest path
        re-embedded every commit message on every index run)."""
        if not ids:
            return set()
        with self._lock(collection):
            try:
                result = self.collection(collection).get(ids=ids)
            except Exception as exc:  # noqa: BLE001 — translate then re-raise
                self._guard(exc)
        return set(result.get("ids", []))

    def delete_by_project(self, project_id: str) -> None:
        """Remove ALL embeddings of a project from every real collection.

        v1.17.6: the GC previously deleted from a phantom `knowledge`
        collection (never used by ingestion), so dropped projects left
        orphaned vectors in `file_summaries` and friends forever.
        """
        for name in COLLECTIONS:
            with self._lock(name):
                try:
                    self.collection(name).delete(where={"project_id": project_id})
                except Exception as exc:  # noqa: BLE001 — translate then re-raise
                    self._guard(exc)
        self._invalidate_health()

    def count(self, collection: str) -> int:
        with self._lock(collection):
            try:
                return self.collection(collection).count()
            except Exception as exc:  # noqa: BLE001 — translate then re-raise
                self._guard(exc)

    def reset(self, name: str) -> None:
        """Drop one collection and forget its cached handle.

        v1.17.6.2: a damaged store can also raise `InternalError` while
        dropping — the collection is being discarded anyway, so treat that
        as success (a fresh `get_or_create_collection` rebuilds it).
        """
        with self._lock(name):
            self._collections.pop(name, None)
            try:
                self._client.delete_collection(name)
            except (ValueError, NotFoundError):
                pass  # collection does not exist — nothing to drop
            except InternalError as exc:
                logger.warning(
                    "Collection %s drop hit a broken store (%s); treating as reset",
                    name,
                    exc,
                )
        self._invalidate_health()

    def reset_all(self) -> None:
        """Drop every knowledge collection (v1.17.6 recovery path)."""
        for name in COLLECTIONS:
            self.reset(name)

    def health(self) -> dict[str, Any]:
        """Probe each non-empty collection's HNSW index (cached).

        `count()` reads the metadata store, so a collection whose segment
        data files vanished still reports a count. v1.17.6 used a cheap
        `get(limit=1)` probe — but that path can pass while the query path
        raises (`Nothing found on disk`), leaving the dashboard healthy and
        the next chat query 503ing (v1.17.6.2). The probe now runs a real
        query with a stored embedding — the exact operation search uses.
        A damaged collection reports under `broken`; the dashboard then
        offers a rebuild instead of failing silently on the next query.
        """
        with self._health_lock:
            if self._health_cache is not None:
                return self._health_cache
        checked: list[str] = []
        broken: list[str] = []
        for name in COLLECTIONS:
            try:
                with self._lock(name):
                    if self.collection(name).count() == 0:
                        continue
                    checked.append(name)
                    # Run the real query path: read one stored embedding,
                    # then query with it (v1.17.6.2 probe).
                    sample = self.collection(name).get(limit=1, include=["embeddings"])
                    vectors = (sample.get("embeddings") or [None])[0]
                    if vectors is None:
                        broken.append(name)
                        continue
                    self.collection(name).query(query_embeddings=[vectors], n_results=1)
            except RagIndexError:
                broken.append(name)
            except InternalError:
                broken.append(name)
            except Exception:  # noqa: BLE001 — not Chroma-internal: not damage
                pass
        result = {"healthy": not broken, "broken": broken, "checked": checked}
        with self._health_lock:
            self._health_cache = result
        return result
