"""Ingest barrier — one instant for the SQLite/Chroma pair (audit A6).

A backup is only a recovery guarantee if the two stores it snapshots
describe the same instant. SQLite's online backup API is point-in-time
correct on its own; Chroma is copied file-by-file *afterwards*. Between
those two copies a knowledge half-write can land — a file's `embedding_id`
committed, its vectors upserted — and the restored pair then claims vectors
that are not in the restored Chroma store, or keeps vectors whose rows are
gone (orphans that still answer questions from deleted files).

So the pair is the unit, not the file. This module is a read/write barrier:

* every span that pairs a knowledge write with its vectors holds
  `ingest_transaction()` — the read side. Several may run concurrently, as
  before, on different collections;
* a backup takes `maintenance_window()` — the write side — around *both*
  snapshots, so an ingest pair either completed before it or starts after
  it. Neither half can straddle the gap.

Write-preferring: a backup waiting for the write side makes new readers
wait, so a continuous indexing stream cannot starve it. The read side is
reentrant *per thread* (`ingest_files` calls `_retract_obsolete_chunks`
inside its own transaction), otherwise a nested acquisition would block
against its own waiting writer.

Stated honestly: this covers the spans that mutate Chroma, which is what
"wait for active Chroma writes to finish" requires. Rows written *outside*
those spans (a test result, a security finding, a git commit) are embedded
later by `_upsert_simple`, so a backup landing in that window restores a
row without its vector. That is safe by construction — none of those
collections carries a skip-if-present marker, so the next index pass
re-embeds them idempotently. The marker (`ProjectFile.embedding_id`) is
what makes a lost half-write permanent, and it is inside the barrier.
"""

import threading
import time
from contextlib import contextmanager
from typing import Iterator

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class KnowledgeBusyError(RuntimeError):
    """The knowledge index never quiesced long enough to snapshot.

    Raised by `maintenance_window()` instead of letting a backup proceed:
    a zip whose SQLite half and Chroma half describe different instants is
    worse than no backup at all, because it looks recoverable and is not.
    The caller reports it and writes nothing.
    """


class Barrier:
    """Write-preferring read/write lock, reentrant on the read side."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        # Reader depth per thread: reentrancy must not deadlock the thread
        # against a writer it is itself blocking.
        self._readers: dict[int, int] = {}
        self._writer: int | None = None
        self._writers_waiting = 0

    @contextmanager
    def reading(self) -> Iterator[None]:
        me = threading.get_ident()
        with self._cond:
            if self._readers.get(me) or self._writer == me:
                # Already holding it on this thread (or holding the write
                # side): count up instead of waiting behind a writer that
                # this very thread is blocking.
                self._readers[me] = self._readers.get(me, 0) + 1
            else:
                while self._writer is not None or self._writers_waiting:
                    self._cond.wait()
                self._readers[me] = 1
        try:
            yield
        finally:
            with self._cond:
                remaining = self._readers.get(me, 1) - 1
                if remaining > 0:
                    self._readers[me] = remaining
                else:
                    self._readers.pop(me, None)
                    if not self._readers:
                        # A writer may be waiting on exactly this.
                        self._cond.notify_all()

    @contextmanager
    def writing(self, timeout: float) -> Iterator[None]:
        with self._cond:
            self._writers_waiting += 1
            try:
                deadline = time.monotonic() + timeout
                while self._writer is not None or self._readers:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise KnowledgeBusyError(
                            "knowledge index still active after "
                            f"{timeout:.0f}s — no consistent snapshot taken"
                        )
                    self._cond.wait(remaining)
            finally:
                self._writers_waiting -= 1
            self._writer = threading.get_ident()
        try:
            yield
        finally:
            with self._cond:
                self._writer = None
                self._cond.notify_all()


_barrier = Barrier()

# Generous on purpose: one project's embedding pass can legitimately run for
# many minutes (thousands of files at ~5 docs/s against a local Ollama). The
# timeout decides when a backup gives up, not how long a half-write may last.
DEFAULT_TIMEOUT = 900.0


@contextmanager
def ingest_transaction() -> Iterator[None]:
    """Mark the span in which a SQLite knowledge write and its vectors are
    one fact. A backup cannot snapshot in the middle of it."""
    with _barrier.reading():
        yield


@contextmanager
def maintenance_window(timeout: float | None = None) -> Iterator[None]:
    """Quiesce the knowledge index; both stores are stable until released.

    Waits at most `timeout` (default `settings.backup_barrier_timeout_seconds`)
    for in-flight ingest pairs to finish, then blocks new ones. Raises
    `KnowledgeBusyError` rather than snapshotting an inconsistent instant.
    """
    limit = (
        float(timeout)
        if timeout is not None
        else float(settings.backup_barrier_timeout_seconds)
    )
    started = time.monotonic()
    with _barrier.writing(limit):
        waited = time.monotonic() - started
        if waited > 1.0:
            # The pass was blocked, not idle — worth knowing when a backup
            # takes minutes for reasons that are not disk speed.
            logger.info("Knowledge index quiesced after %.1fs; snapshotting", waited)
        yield
