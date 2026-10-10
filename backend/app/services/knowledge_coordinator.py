"""Per-project coordination for knowledge indexing (v1.17.19.7, audit A3/A4).

Two P1 findings share one root cause: nothing serialized knowledge work for a
project, and nothing told a running index that the index had been wiped under
it.

**A3 — per-project mutual exclusion.** Startup auto-index, repo sync, the
`/rag/index` button, `/rag/index/all` and the CLI can all queue the same
project, so two pool workers read the same pending files, embedded the same
content twice and raced on `embedding_id` / the Chroma collection. The
collection-level lock in `ChromaManager` serializes I/O, not the logical
indexing transaction. `knowledge_lock` is a per-project `RLock`.

**A4 — reset/index generation barrier.** `run_reset_knowledge` dropped the
collections but deliberately left running jobs alive, so an in-flight index
wrote its vectors straight back into the freshly wiped store — neither the
pre-reset state nor a clean post-reset state. `bump_generation()` invalidates
every in-flight run; an index run captures `current_generation()` when it
starts and `assert_current()` refuses to write once its generation is stale.

Both are **process-local on purpose**: Sentinel indexes from the one uvicorn
process `run.py` starts, and the races live in its in-process thread pool.
Cross-process mutual exclusion would need a filesystem lock, which is more
machinery than these two findings justify (Rule 8).

`knowledge_lock` delegates to `services/project_operations.py` (v1.17.19.10,
audit A7) so that one registry owns every per-project slot. The generation
counter stays here — it is specific to resetting the knowledge index and has
no analogue for builds or scans.
"""

import threading
from contextlib import contextmanager

from app.services.project_operations import (
    project_operation,
    reset_for_tests as _reset_locks,
)


class KnowledgeResetInterrupt(Exception):
    """Raised when a knowledge-index run loses to a reset mid-flight (A4).

    Distinct from a failure: the run aborts *before* writing, so the store
    keeps the reset's clean slate instead of being repopulated half-way."""


_guard = threading.Lock()
_locks: dict[str, threading.RLock] = {}
_running: set[str] = set()
_generation: int = 0


def _lock_for(project_id: str) -> threading.RLock:
    with _guard:
        lock = _locks.get(project_id)
        if lock is None:
            # Re-entrant: index_project -> ingest_files may nest, and the
            # CLI path can hold it across a summary regeneration.
            lock = threading.RLock()
            _locks[project_id] = lock
        return lock


def is_indexing(project_id: str) -> bool:
    """True from the moment an index run claims a project until it releases
    it — including while it waits on the lock (A3)."""
    with _guard:
        return project_id in _running


@contextmanager
def knowledge_lock(project_id: str):
    """One knowledge-index execution per project (A3/A7).

    A duplicate request blocks until the first finishes, then runs and finds
    everything already embedded — so exactly one set of embeddings is produced
    and `embedding_id` is never raced. Delegates to the shared per-project
    operation coordinator (audit A7) so build/tester/test guards and this one
    cannot disagree about what is running for a project."""
    with project_operation(project_id, "knowledge"):
        with _guard:
            _running.add(project_id)
        try:
            yield
        finally:
            with _guard:
                _running.discard(project_id)


def current_generation() -> int:
    with _guard:
        return _generation


def bump_generation() -> int:
    """Invalidate every in-flight index run (called by the reset task, A4)."""
    global _generation
    with _guard:
        _generation += 1
        return _generation


def is_stale(generation: int) -> bool:
    """Has the knowledge index been reset since `generation` was captured?"""
    return generation != current_generation()


def assert_current(generation: int, project_name: str) -> None:
    """Guard a write: a stale run must leave the reset slate untouched (A4)."""
    if is_stale(generation):
        raise KnowledgeResetInterrupt(
            f"knowledge index for {project_name} aborted — "
            "the index was reset mid-run"
        )


def reset_for_tests() -> None:
    """Drop locks, the running set and the generation counter (test isolation)."""
    global _generation
    _reset_locks()
    with _guard:
        _running.clear()
        _generation = 0
