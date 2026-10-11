"""Deterministic Chroma rebuild verification (audit Batch 3, v1.17.19.19).

The property under test is the audit's own: the promise "knowledge exists" is
checkable, not assumed. Every divergence direction is covered — flag with no
vector, vector with no row, and an unreadable store — plus the repair that
turns the first two back into a consistent index without re-embedding the
world, and the fact that an empty index after a reset is not a failure.
"""

from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.db import connection
from app.db.models import Project, ProjectFile
from app.db.connection import get_engine
from app.services.chroma_manager import ChromaManager, get_chroma_manager
from app.services.knowledge_integrity import (
    reconcile_store,
    verify_pairing,
    verify_store,
)

_VECTOR = [0.1] * 8


def _dispose_engine():
    engine = connection._engine
    connection._engine = None
    if engine is not None:
        engine.dispose()


@pytest.fixture()
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data"
    (root / "sqlite").mkdir(parents=True)
    monkeypatch.setattr(settings, "db_path", root / "sqlite" / "sentinel.db")
    monkeypatch.setattr(settings, "chroma_path", root / "chroma")
    _dispose_engine()
    connection.init_db()
    yield root
    _dispose_engine()


def _seed(
    root: Path,
    *,
    flag: bool,
    vector: bool,
    content: str = "print(1)\n",
) -> str:
    """One file row, with/without the embedding flag and its vector.

    Returns the row id the vector is stored under (`{row_id}#0`, the id
    scheme `ingest_files` actually uses). The file is really written, because
    the invariant reads the disk to tell "nothing to embed" (a zero-byte
    `__init__.py`) from a missing vector.
    """
    source = root / "src"
    source.mkdir(parents=True, exist_ok=True)
    absolute = source / "app.py"
    absolute.write_text(content, encoding="utf-8")
    with Session(get_engine()) as session:
        project = Project(name="sentinel", path=str(source), language="Python")
        session.add(project)
        session.flush()
        pid = project.id
        row = ProjectFile(
            project_id=pid,
            path="app.py",
            absolute_path=str(absolute),
        )
        session.add(row)
        session.flush()
        row_id = row.id
        if flag:
            row.embedding_id = row_id
        session.commit()
    if vector:
        ChromaManager(root / "chroma").upsert(
            "file_summaries",
            ids=[f"{row_id}#0"],
            embeddings=[_VECTOR],
            documents=["app.py\nprint(1)"],
            metadatas=[{"project_id": pid, "file_path": "app.py"}],
        )
    return row_id


# --- the report ------------------------------------------------------------


def test_verify_store_reports_consistent_pairing(data_root):
    _seed(data_root, flag=True, vector=True)
    report = verify_store()
    assert report.consistent
    assert report.checked_files == 1 and report.checked_vectors == 1
    assert report.collection_counts["file_summaries"] == 1


def test_verify_store_finds_a_flag_with_no_vector(data_root):
    """A6's failure shape: the flag promises a vector that is not there."""
    _seed(data_root, flag=True, vector=False)
    report = verify_store()
    assert not report.consistent
    assert report.diverged
    assert len(report.missing) == 1


def test_verify_store_finds_a_vector_with_no_row(data_root):
    _seed(data_root, flag=True, vector=True)
    with Session(get_engine()) as session:
        row = session.exec(select(ProjectFile)).one()
        session.delete(row)
        session.commit()
    report = verify_store()
    assert not report.consistent
    assert len(report.orphans) == 1


def test_verify_store_after_a_reset_is_not_a_failure(data_root):
    """An empty index is the *correct* post-reset state: nothing is claimed,
    so there is nothing missing. This is the case that must not spam the
    startup log as a failure."""
    _seed(data_root, flag=False, vector=False)
    report = verify_store()
    assert report.consistent
    assert not report.diverged
    assert report.summary().startswith("knowledge pairing consistent")


def test_an_empty_file_with_a_flag_is_not_a_divergence(data_root):
    """`ingest_files` deliberately marks a zero-byte file as embedded without
    upserting a vector, so the pending query stops re-queueing the project.
    Treating that as divergence made the real index report 110 missing files
    on every boot — an invariant that cries wolf is worse than none."""
    _seed(data_root, flag=True, vector=False, content="")
    report = verify_store()
    assert report.consistent, report.summary()
    assert not report.diverged
    # And a file that has since disappeared is the same case.
    source = data_root / "src" / "app.py"
    source.unlink()
    assert verify_store().consistent


def test_a_vanished_file_with_a_flag_is_not_a_divergence(data_root):
    _seed(data_root, flag=True, vector=False)
    source = data_root / "src" / "app.py"
    source.unlink()
    assert verify_store().consistent


def test_verify_store_handles_an_unopenable_database(data_root):
    db = data_root / "sqlite" / "sentinel.db"
    db.write_bytes(b"not a database at all, but a file that exists")
    report = verify_store()
    assert not report.consistent


def test_verify_store_reads_a_specific_manager(data_root):
    """The API route passes the service's own manager; the check must follow
    it rather than reaching for the shared singleton (v1.17.7.3 lesson)."""
    _seed(data_root, flag=True, vector=True)
    injected = ChromaManager(data_root / "chroma")
    report = verify_store(chroma=injected)
    assert report.consistent
    assert report.collection_counts["file_summaries"] == 1


def test_verify_pairing_still_checks_a_path_not_a_manager(data_root):
    """Restore still uses the staged-path form (A6)."""
    _seed(data_root, flag=True, vector=True)
    report = verify_pairing(data_root / "sqlite" / "sentinel.db", data_root / "chroma")
    assert report.consistent


# --- the repair ------------------------------------------------------------


def test_reconcile_clears_the_flag_and_re_embed_is_possible(data_root):
    _seed(data_root, flag=True, vector=False)
    result = reconcile_store()
    assert result.cleared_flags == 1
    after = verify_store()
    assert after.consistent
    with Session(get_engine()) as session:
        row = session.exec(select(ProjectFile)).one()
        assert row.embedding_id is None  # ingest_files will pick it up again


def test_reconcile_removes_orphaned_vectors(data_root):
    _seed(data_root, flag=True, vector=True)
    with Session(get_engine()) as session:
        row = session.exec(select(ProjectFile)).one()
        session.delete(row)
        session.commit()
    result = reconcile_store()
    assert result.removed_vectors == 1
    assert verify_store().consistent
    assert get_chroma_manager().count("file_summaries") == 0


def test_reconcile_is_a_no_op_when_already_consistent(data_root):
    _seed(data_root, flag=True, vector=True)
    result = reconcile_store()
    assert result.cleared_flags == 0 and result.removed_vectors == 0
    assert "already consistent" in result.summary()


def test_reconcile_holds_the_ingest_barrier(data_root):
    """The repair is a knowledge write, so a backup must not be able to
    snapshot it half-done (A6's barrier applies here too)."""
    from app.services.ingest_barrier import maintenance_window

    _seed(data_root, flag=True, vector=False)
    granted = maintenance_window(timeout=10.0)
    granted.__enter__()
    try:
        finished = []

        def repair():
            finished.append(reconcile_store())

        import threading

        handle = threading.Thread(target=repair)
        handle.start()
        handle.join(0.4)
        assert not finished, "reconcile ran inside a held maintenance window"
    finally:
        granted.__exit__(None, None, None)


def test_reconcile_reports_rather_than_repairs_an_unreadable_store(
    data_root, monkeypatch
):
    """A store that cannot execute a query is a rebuild, not a repair — the
    reset route is the honest path and reconcile must not half-handle it."""
    _seed(data_root, flag=True, vector=True)
    # Simulate the damaged store ChromaManager.health() is what detects; its
    # own damage detection is covered in test_chroma_manager. What matters
    # here is that reconcile refuses to *repair* what it cannot read.
    monkeypatch.setattr(
        ChromaManager,
        "health",
        lambda self: {
            "healthy": False,
            "broken": ["file_summaries"],
            "checked": ["file_summaries"],
        },
    )
    result = reconcile_store()
    assert result.cleared_flags == 0 and result.removed_vectors == 0
    assert result.after is not None
    assert result.after.unreadable
    assert not result.after.consistent


# --- startup + API surfaces ------------------------------------------------


def test_startup_check_reports_a_divergence(data_root):
    from app.services.startup_check import _check_knowledge_pairing

    _seed(data_root, flag=True, vector=False)
    status = _check_knowledge_pairing()
    assert status.ok is False
    assert "missing vectors" in status.detail
    assert "reconcile" in status.detail


def test_startup_check_reports_an_empty_index_as_ok(data_root):
    from app.services.startup_check import _check_knowledge_pairing

    _seed(data_root, flag=False, vector=False)
    status = _check_knowledge_pairing()
    assert status.ok is True


def test_startup_check_never_raises_when_the_store_is_broken(data_root):
    from app.services.startup_check import _check_knowledge_pairing

    db = data_root / "sqlite" / "sentinel.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_bytes(b"definitely not sqlite")
    status = _check_knowledge_pairing()
    assert status.ok is False
    assert isinstance(status.detail, str) and status.detail


def test_rag_index_status_includes_the_pairing(data_root):
    _seed(data_root, flag=True, vector=True)
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as client:
        response = client.get("/api/v1/rag/index/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["pairing"]["consistent"] is True
    assert payload["pairing"]["collection_counts"]["file_summaries"] == 1
    assert "consistent" in payload["pairing"]["summary"]
    _dispose_engine()
