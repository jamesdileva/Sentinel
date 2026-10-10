"""Per-project operation coordination (v1.17.19.10, audit A7).

Build/Test/Scan/Tester jobs all run for a single project, but nothing stopped
two of them running at once. The API is not the authority here — the in-process
job pool is what actually executes them — so the guard lives in the tasks, with
a fast read-only probe the API can use to refuse a duplicate before it is even
queued.

The audit's compatibility matrix, implemented as data:

| Operation | Same operation  | Cross operation            |
|-----------|-----------------|----------------------------|
| Build     | reject          | blocks tester              |
| Tester    | reject          | blocks build               |
| Test      | reject          | allows security scan       |
| Security  | coalesce        | allows everything          |
| Knowledge | coalesce        | allows everything          |

Two policies, because "reject" and "coalesce" mean genuinely different things:

- **reject** — the second request fails fast. A build that cannot run burns
  real side effects (killing port listeners, launching servers, replacing
  log rows), so a queued duplicate is worse than a visible error.
- **coalesce** — the duplicate waits on a per-operation lock, then runs and
  finds the work already done. Scans and indexing are idempotent reads plus
  writes, so waiting is both safe and cheaper than re-running.

**Not a global lock.** Each guard is keyed by (project, operation), so a build
in flight for project A never delays a build for project B.

**No blocking cycles.** Rejecting operations never wait, so the only possible
wait is a coalescing operation on its own lock. The single place that holds
more than one guard is `run_reset_knowledge`, which takes every project's
knowledge lock in a fixed order and acquires nothing else while holding them.

Process-local, like `knowledge_coordinator`: Sentinel runs one uvicorn process
and these races live in its thread pool (Rule 8).
"""

import threading
from contextlib import contextmanager

# Operations whose cross-conflicts are refused rather than queued.
# The key is the operation being requested; the value is the set of operations
# it will refuse to run alongside (including itself).
_REJECTS: dict[str, frozenset[str]] = {
    # build->open kills listeners, launches servers and replaces log rows, so
    # two builds - or a build driving the UI while a tester does - interfere.
    "build": frozenset({"build", "tester"}),
    "tester": frozenset({"build", "tester"}),
    # A test run is a command with a timeout; duplicates only waste the pool.
    "test": frozenset({"test"}),
}

# Idempotent enough that a duplicate can simply wait for the first to finish.
_COALESCED = frozenset({"security", "knowledge"})

ALL_OPERATIONS = frozenset(_REJECTS) | _COALESCED


class OperationBusyError(Exception):
    """A conflicting operation is already running for this project (A7).

    Carries the requested operation and the operations that blocked it, so
    the caller can report both rather than a generic 'busy'.
    """

    def __init__(self, operation: str, blocked_by: list[str]) -> None:
        self.operation = operation
        self.blocked_by = sorted(blocked_by)
        super().__init__(
            f"{operation} cannot start for this project while "
            f"{', '.join(self.blocked_by)} is running"
        )


_guard = threading.Lock()
_locks: dict[tuple[str, str], threading.RLock] = {}
_held: dict[str, set[str]] = {}


def _lock_for(project_id: str, operation: str) -> threading.RLock:
    key = (project_id, operation)
    with _guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock


def _conflicts(project_id: str, operation: str) -> set[str]:
    """Operations currently held for this project that `operation` refuses."""
    with _guard:
        held = set(_held.get(project_id) or ())
    return _REJECTS.get(operation, frozenset()) & held


def is_running(project_id: str, operation: str | None = None) -> bool:
    """True while an operation holds this project's slot.

    `operation=None` reports *any* operation, which is what the build button
    uses to tell the user the project is busy without knowing what with."""
    with _guard:
        held = _held.get(project_id) or set()
        if operation is None:
            return bool(held)
        return operation in held


def active_operations(project_id: str) -> list[str]:
    """Names of the operations currently holding this project (deterministic)."""
    with _guard:
        return sorted(_held.get(project_id) or ())


@contextmanager
def project_operation(project_id: str, operation: str):
    """Claim this project for `operation`, or refuse/queue per the matrix.

    Raises OperationBusyError for a rejected conflict. Coalesced operations
    wait their turn, so a duplicate scan never redoes the first one's work.
    """
    if operation not in ALL_OPERATIONS:
        raise ValueError(f"Unknown project operation: {operation!r}")

    if operation in _REJECTS:
        blocked = _conflicts(project_id, operation)
        if blocked:
            raise OperationBusyError(operation, blocked)
        with _guard:
            _held.setdefault(project_id, set()).add(operation)
        try:
            yield
        finally:
            with _guard:
                remaining = _held.get(project_id)
                if remaining is not None:
                    remaining.discard(operation)
                    if not remaining:
                        _held.pop(project_id, None)
        return

    # Coalesced: mark the slot as taken before waiting, so a second request
    # sees it and queues rather than running in parallel.
    lock = _lock_for(project_id, operation)
    with _guard:
        _held.setdefault(project_id, set()).add(operation)
    try:
        with lock:
            yield
    finally:
        with _guard:
            remaining = _held.get(project_id)
            if remaining is not None:
                remaining.discard(operation)
                if not remaining:
                    _held.pop(project_id, None)


def reset_for_tests() -> None:
    """Drop every lock and in-flight record (test isolation)."""
    global _held
    with _guard:
        _locks.clear()
        _held = {}
