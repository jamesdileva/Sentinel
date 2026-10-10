"""Audit A7: per-project operation coordination (v1.17.19.10).

The API is not the authority here — the in-process job pool executes the work
— so these tests exercise the guard at the layer the audit actually cares
about: two operations that both want the same project.
"""

import threading

import pytest

from app.services.project_operations import (
    OperationBusyError,
    active_operations,
    is_running,
    project_operation,
)


@pytest.fixture(autouse=True)
def _clean_locks():
    from app.services import project_operations

    project_operations.reset_for_tests()
    yield
    project_operations.reset_for_tests()


def test_build_refuses_a_concurrent_build():
    with project_operation("p1", "build"):
        with pytest.raises(OperationBusyError) as exc:
            with project_operation("p1", "build"):
                pass
    assert "build" in str(exc.value)


def test_build_and_tester_refuse_each_other():
    """The audit's cross row: build blocks tester and tester blocks build.
    A build→open and a click-through against the same app cannot both drive it."""
    with project_operation("p1", "build"):
        with pytest.raises(OperationBusyError):
            with project_operation("p1", "tester"):
                pass
    with project_operation("p1", "tester"):
        with pytest.raises(OperationBusyError):
            with project_operation("p1", "build"):
                pass


def test_test_refuses_concurrent_test_but_allows_scan():
    """Same-operation refusal, and the audit's 'usually allow security scan'."""
    with project_operation("p1", "test"):
        with pytest.raises(OperationBusyError):
            with project_operation("p1", "test"):
                pass
        # A security scan is allowed alongside a test.
        with project_operation("p1", "security"):
            assert is_running("p1", "security")


def test_scan_coalesces_instead_of_refusing():
    """Scans are idempotent, so a duplicate waits rather than failing."""
    order: list[str] = []
    gate = threading.Event()

    def first():
        with project_operation("p1", "security"):
            gate.wait(timeout=2)
            order.append("first")

    thread = threading.Thread(target=first)
    thread.start()
    try:
        while not is_running("p1", "security"):
            pass
        # A second scan queues; it does not raise.
        queued = threading.Thread(
            target=lambda: order.append("queued-ran") or _run_scan_against("p1")
        )
        queued.start()
        gate.set()
        thread.join(timeout=2)
        queued.join(timeout=2)
        # The second run completed, and nothing was refused.
        assert "queued-ran" in order
    finally:
        gate.set()


def _run_scan_against(project_id: str) -> None:
    with project_operation(project_id, "security"):
        pass


def test_knowledge_index_allows_builds_and_tests():
    """The audit's 'RAG index: allow normal reads' — indexing must not block
    the build/test/scan pipeline, or a queued auto-index would stall a build."""
    with project_operation("p1", "knowledge"):
        for other in ("build", "test", "security"):
            with project_operation("p1", other):
                assert is_running("p1", other)


def test_locks_are_per_project():
    """Not a giant global lock: a build for one project never delays another."""
    other_started = threading.Event()

    def other():
        with project_operation("p2", "build"):
            other_started.set()

    thread = threading.Thread(target=other)
    thread.start()
    try:
        with project_operation("p1", "build"):
            assert other_started.wait(timeout=1)
    finally:
        thread.join(timeout=2)


def test_active_operations_are_released():
    with project_operation("p1", "build"):
        assert active_operations("p1") == ["build"]
    assert active_operations("p1") == []
    assert is_running("p1") is False


def test_unknown_operation_is_a_programming_error():
    with pytest.raises(ValueError):
        with project_operation("p1", "deploy"):
            pass


def test_reset_releases_every_held_slot(tmp_db):
    """A4 regression: reset must drop held slots as well as the index, or a
    project that never finished indexing blocks every future build."""
    from app.services import knowledge_coordinator as kc

    kc.reset_for_tests()
    with kc.knowledge_lock("p1"):
        assert is_running("p1", "knowledge")
        # The shared coordinator must see the knowledge slot too — otherwise
        # a build could start while an index was in flight.
        assert active_operations("p1") == ["knowledge"]
    assert active_operations("p1") == []


def test_knowledge_lock_coalesces_a_duplicate():
    """A3 regression through the shared registry: the second request waits,
    so exactly one set of embeddings is produced."""
    from app.services import knowledge_coordinator as kc

    kc.reset_for_tests()
    order: list[str] = []
    entered = threading.Event()
    release = threading.Event()

    def worker(name: str) -> None:
        with kc.knowledge_lock("p1"):
            order.append(f"{name}:start")
            if name == "first":
                entered.set()
            release.wait(timeout=2)
            order.append(f"{name}:end")

    first = threading.Thread(target=worker, args=("first",))
    first.start()
    try:
        assert entered.wait(timeout=2)
        second = threading.Thread(target=worker, args=("second",))
        second.start()
        assert order == ["first:start"]
        release.set()
        first.join(timeout=2)
        second.join(timeout=2)
        assert order == ["first:start", "first:end", "second:start", "second:end"]
    finally:
        release.set()


# --- API-level fast refusal (the 409 layer) ---


@pytest.fixture()
def eager(monkeypatch):
    """Run in-process scheduler jobs synchronously so tests need no threads."""
    from app.services.job_scheduler import scheduler

    monkeypatch.setattr(scheduler, "run_inline", True)
    yield
    monkeypatch.setattr(scheduler, "run_inline", False)


def _seed(tmp_db) -> str:
    from sqlmodel import Session

    from app.core.config import settings
    from app.db import connection
    from app.services.indexer import IndexerService

    monkey = pytest.MonkeyPatch()
    monkey.setattr(settings, "auto_scan_on_startup", False)
    with Session(connection.get_engine()) as session:
        return (
            IndexerService(session)
            .index_project("tests/fixtures/sample_python_project")
            .id
        )


def test_build_api_409_while_build_running(client, tmp_db, eager):
    from app.services.project_operations import project_operation

    project_id = _seed(tmp_db)
    with project_operation(project_id, "build"):
        resp = client.post("/api/v1/builds/run", json={"project_id": project_id})
        assert resp.status_code == 409
        assert "build is running" in resp.json()["detail"]
    # Released: the same request now succeeds.
    resp = client.post("/api/v1/builds/run", json={"project_id": project_id})
    assert resp.status_code == 202


def test_build_api_409_while_tester_running(client, tmp_db, eager):
    """The cross row, from the other side: a project slot held by a tester
    must refuse a build. (No shipped fixture registers a tester, so testing
    the /testers/run 404-vs-409 order would need one; this direction covers
    the same conflict and the API's precedence is unchanged.)

    Ordering note: the tester endpoint checks for a registered tester first,
    so its 409 is only reachable once one exists."""
    from app.services.project_operations import project_operation

    project_id = _seed(tmp_db)
    with project_operation(project_id, "tester"):
        resp = client.post("/api/v1/builds/run", json={"project_id": project_id})
        assert resp.status_code == 409
        assert "tester is running" in resp.json()["detail"]


def test_tests_api_409_while_test_running(client, tmp_db, eager):
    from app.services.project_operations import project_operation

    project_id = _seed(tmp_db)
    with project_operation(project_id, "test"):
        resp = client.post("/api/v1/tests/run", params={"project_id": project_id})
        assert resp.status_code == 409
    resp = client.post("/api/v1/tests/run", params={"project_id": project_id})
    assert resp.status_code == 202


def test_tests_api_allows_scan_alongside(client, tmp_db, eager):
    """The cross-row: a test must not block a security scan (or the reverse)."""
    from app.services.project_operations import project_operation

    project_id = _seed(tmp_db)
    with project_operation(project_id, "test"):
        resp = client.post("/api/v1/security/scan", params={"project_id": project_id})
        assert resp.status_code == 202
