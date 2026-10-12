"""Restore + knowledge-integrity tests (audit A6).

The property under test is the audit's own: a restored backup either arrives
as one consistent instant (SQLite's embedding flags and Chroma's vectors
agree), or the vectors are not installed and the next knowledge pass
re-embeds them. Nothing in between.
"""

import json
import threading
import zipfile
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.db import connection
from app.db.models import Project, ProjectFile
from app.db.connection import get_engine
from app.services.backup_service import create_backup
from app.services.chroma_manager import ChromaManager
from app.services.ingest_barrier import ingest_transaction
from app.services.knowledge_integrity import verify_pairing
from app.services.restore_service import (
    REBUILT,
    RESTORED,
    RestoreError,
    restore_backup,
)

_VECTOR = [0.1] * 8


def _dispose_engine():
    engine = connection._engine
    connection._engine = None
    if engine is not None:
        engine.dispose()


@pytest.fixture()
def data_root(tmp_path, monkeypatch):
    """A data/ directory laid out the way the real one is, so every derived
    path (backups, chroma, screenshots, logs) follows from the db path."""
    root = tmp_path / "data"
    (root / "sqlite").mkdir(parents=True)
    monkeypatch.setattr(settings, "db_path", root / "sqlite" / "sentinel.db")
    monkeypatch.setattr(settings, "chroma_path", root / "chroma")
    _dispose_engine()
    connection.init_db()
    yield root
    _dispose_engine()


def _seed_knowledge(root: Path, missing_vectors: bool = False):
    """One project, one embedded file row, one vector for it.

    `missing_vectors=False` leaves the pairing intact; True writes the flag
    without its vector — the state A6 exists to catch. The file is written to
    disk too, so it counts as embeddable (a zero-byte or vanished file
    legitimately carries a flag with no vector).
    """
    source = root / "src"
    source.mkdir(parents=True, exist_ok=True)
    absolute = source / "app.py"
    absolute.write_text("print(1)\n", encoding="utf-8")
    with Session(get_engine()) as session:
        project = Project(name="sentinel", path=str(source), language="Python")
        session.add(project)
        session.flush()
        project_id = project.id
        row = ProjectFile(
            project_id=project_id,
            path="app.py",
            absolute_path=str(absolute),
        )
        session.add(row)
        session.flush()
        # The contract under test: `ingest_files` marks the row with its own
        # id and stores vectors as `{row.id}#{chunk}`.
        row_id = row.id
        row.embedding_id = row_id
        session.commit()
    if not missing_vectors:
        ChromaManager(root / "chroma").upsert(
            "file_summaries",
            ids=[f"{row_id}#0"],
            embeddings=[_VECTOR],
            documents=["app.py\nprint(1)"],
            metadatas=[{"project_id": project_id, "file_path": "app.py"}],
        )
    return project_id


def _backup(root: Path, **kwargs) -> Path:
    result = create_backup(keep=1, **kwargs)
    assert result["skipped"] == [], result["skipped"]
    return Path(result["path"])


# --- knowledge integrity ---------------------------------------------------


def test_pairing_holds_when_flag_and_vector_both_exist(data_root):
    _seed_knowledge(data_root)
    report = verify_pairing(data_root / "sqlite" / "sentinel.db", data_root / "chroma")
    assert report.consistent
    assert report.checked_files == 1
    assert report.summary().startswith("knowledge pairing consistent")


def test_missing_vector_is_reported_not_assumed(data_root):
    """The A6 failure shape: the flag promises a vector that is not there.
    Left undetected, `ingest_files` skips the file forever."""
    _seed_knowledge(data_root, missing_vectors=True)
    report = verify_pairing(data_root / "sqlite" / "sentinel.db", data_root / "chroma")
    assert not report.consistent
    assert len(report.missing) == 1
    assert "app.py" in report.missing[0]


def test_vector_without_a_file_row_is_an_orphan(data_root, tmp_path):
    """A vector whose file row is gone (but whose project is still known) is
    an orphan — the A1 mirror. Its project is intact, so this is a genuine
    leftover, not a mismatched install."""
    project_id = _seed_knowledge(data_root)
    orphan_store = tmp_path / "orphan-store"
    ChromaManager(orphan_store).upsert(
        "file_summaries",
        ids=["ghost#0"],
        embeddings=[_VECTOR],
        documents=["ghost.py"],
        metadatas=[{"project_id": project_id, "file_path": "ghost.py"}],
    )
    with Session(get_engine()) as session:
        row = session.exec(
            select(ProjectFile).where(ProjectFile.path == "app.py")
        ).one()
        session.delete(row)
        session.commit()
    report = verify_pairing(data_root / "sqlite" / "sentinel.db", orphan_store)
    assert not report.consistent
    assert any("ghost" in orphan for orphan in report.orphans)


def test_absent_database_is_not_a_pairing(tmp_path):
    report = verify_pairing(tmp_path / "nope.db", tmp_path / "chroma")
    assert not report.consistent


# --- restore round trip ----------------------------------------------------


def test_round_trip_restores_both_halves(data_root, tmp_path):
    _seed_knowledge(data_root)
    (data_root / "screenshots" / "sentinel").mkdir(parents=True)
    (data_root / "screenshots" / "sentinel" / "a.png").write_bytes(b"png")
    zip_path = _backup(data_root)

    # Restore into a *different* data root, so nothing can pass by accident.
    elsewhere = tmp_path / "restored"
    (elsewhere / "sqlite").mkdir(parents=True)
    settings.db_path = elsewhere / "sqlite" / "sentinel.db"
    settings.chroma_path = elsewhere / "chroma"

    report = restore_backup(zip_path)
    assert report.vectors == RESTORED
    assert (elsewhere / "sqlite" / "sentinel.db").exists()
    assert (elsewhere / "chroma").is_dir()
    assert (elsewhere / "screenshots" / "sentinel" / "a.png").exists()
    assert not (elsewhere / "logs").exists() or (elsewhere / "logs").is_dir()

    restored = verify_pairing(
        elsewhere / "sqlite" / "sentinel.db", elsewhere / "chroma"
    )
    assert restored.consistent, restored.summary()
    _dispose_engine()


def test_backup_zip_carries_a_manifest_and_fixed_screenshot_path(data_root, tmp_path):
    """v1.17.19.17: screenshots were being zipped from <repo>/screenshots —
    a path that does not exist — so every backup silently lost them."""
    _seed_knowledge(data_root)
    (data_root / "screenshots" / "sentinel").mkdir(parents=True)
    (data_root / "screenshots" / "sentinel" / "a.png").write_bytes(b"png")
    zip_path = _backup(data_root)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("backup_manifest.json").decode("utf-8"))
    assert "screenshots/sentinel/a.png" in names
    assert manifest["format"] == 1
    assert manifest["chroma_counts"]["file_summaries"] == 1


def test_restore_refuses_a_file_that_is_not_a_backup(tmp_path):
    not_a_zip = tmp_path / "notes.txt"
    not_a_zip.write_text("hello")
    with pytest.raises(RestoreError):
        restore_backup(not_a_zip)


def test_restore_refuses_a_zip_without_a_database(data_root, tmp_path):
    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as zf:
        zf.writestr("chroma/keepme", "x")
    with pytest.raises(RestoreError):
        restore_backup(empty)


def test_restore_refuses_while_a_server_is_listening(data_root, monkeypatch):
    """Restoring replaces the SQLite file under a live connection."""
    import httpx

    _seed_knowledge(data_root)
    zip_path = _backup(data_root)

    class _Up:
        status_code = 200

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Up())
    with pytest.raises(RestoreError) as exc:
        restore_backup(zip_path)
    assert "running" in str(exc.value)
    # Nothing was installed.
    assert not any("pre-restore" in p.name for p in data_root.iterdir())


def test_pre_a6_backup_rebuilds_vectors(data_root, tmp_path):
    """A zip from before the barrier carries no chroma/ half — the honest
    outcome is a rebuild, not trusting vectors that are not there. A stale
    store left over from the previous database must not survive either."""
    _seed_knowledge(data_root)
    zip_path = _backup(data_root)

    legacy = tmp_path / "legacy.zip"
    with zipfile.ZipFile(zip_path) as src:
        with zipfile.ZipFile(legacy, "w") as dst:
            for name in src.namelist():
                if name.startswith("chroma/") or name == "backup_manifest.json":
                    continue
                dst.writestr(name, src.read(name))

    elsewhere = tmp_path / "legacy-restored"
    (elsewhere / "sqlite").mkdir(parents=True)
    (elsewhere / "chroma").mkdir(parents=True)
    (elsewhere / "chroma" / "stale-marker.txt").write_text("pre-existing")
    settings.db_path = elsewhere / "sqlite" / "sentinel.db"
    settings.chroma_path = elsewhere / "chroma"

    report = restore_backup(legacy)
    assert report.vectors == REBUILT
    assert "no vectors" in (report.vector_reason or "")
    assert not (elsewhere / "chroma").exists()
    assert not (elsewhere / "chroma" / "stale-marker.txt").exists()
    assert any("pre-restore" in item for item in report.moved_aside)
    _dispose_engine()


def test_torn_vector_copy_rebuilds_rather_than_trusts(data_root, tmp_path):
    """A chroma half whose counts no longer match its own manifest is a torn
    copy, and a torn copy must not be installed."""
    _seed_knowledge(data_root)
    zip_path = _backup(data_root)

    torn = tmp_path / "torn.zip"
    with zipfile.ZipFile(zip_path) as src:
        manifest = json.loads(src.read("backup_manifest.json").decode("utf-8"))
        manifest["chroma_counts"]["file_summaries"] = 99  # a lie
        with zipfile.ZipFile(torn, "w") as dst:
            for name in src.namelist():
                if name == "backup_manifest.json":
                    dst.writestr(name, json.dumps(manifest))
                else:
                    dst.writestr(name, src.read(name))

    elsewhere = tmp_path / "torn-restored"
    (elsewhere / "sqlite").mkdir(parents=True)
    settings.db_path = elsewhere / "sqlite" / "sentinel.db"
    settings.chroma_path = elsewhere / "chroma"

    report = restore_backup(torn)
    assert report.vectors == REBUILT
    assert "differ from the manifest" in (report.vector_reason or "")
    assert not (elsewhere / "chroma").exists()
    _dispose_engine()


# --- backup side -----------------------------------------------------------


def test_backup_waits_for_an_in_flight_ingest(data_root):
    """A6's guarantee in the direction that matters: an ingest started
    before the backup either completes first or the backup refuses."""
    started = threading.Event()
    release = threading.Event()

    def ingest():
        started.set()
        with ingest_transaction():
            assert release.wait(5.0)

    handle = threading.Thread(target=ingest)
    handle.start()
    assert started.wait(2.0)
    result_holder = {}

    def run_backup():
        result_holder["result"] = create_backup(keep=1)

    backup_thread = threading.Thread(target=run_backup)
    backup_thread.start()
    # The backup must not finish while the ingest holds the index — it is
    # blocked on the write side of the barrier, not merely slow.
    assert not result_holder
    release.set()
    handle.join(5.0)
    backup_thread.join(20.0)
    assert result_holder["result"]["skipped"] == []
    assert Path(result_holder["result"]["path"]).exists()
    _dispose_engine()


def test_backup_writes_nothing_when_the_index_never_quiesces(data_root, monkeypatch):
    monkeypatch.setattr(settings, "backup_barrier_timeout_seconds", 0)
    _seed_knowledge(data_root)
    before = sorted((data_root / "backups").glob("*.zip"))

    hold = threading.Event()

    def ingest():
        with ingest_transaction():
            assert hold.wait(5.0)

    handle = threading.Thread(target=ingest)
    handle.start()
    try:
        result = create_backup(keep=7)
    finally:
        hold.set()
        handle.join(5.0)
    assert result["skipped"], result
    assert not Path(result["path"]).exists()
    assert sorted((data_root / "backups").glob("*.zip")) == before


def test_ingest_files_actually_holds_the_barrier(data_root):
    """The wiring test: holding the write side must block a real
    `RagService.ingest_files` run, not just a bare `ingest_transaction`."""
    from app.services.ingest_barrier import maintenance_window
    from app.services.rag_service import RagService

    with Session(get_engine()) as session:
        project = Project(name="wired", path=str(data_root / "src"), language="Python")
        session.add(project)
        session.flush()
        pid = project.id
        session.add(
            ProjectFile(
                project_id=pid,
                path="missing.py",
                absolute_path=str(data_root / "src" / "missing.py"),
            )
        )
        session.commit()

    release = threading.Event()
    window_held = threading.Event()

    def hold_window():
        window_held.set()
        with maintenance_window(timeout=10.0):
            assert release.wait(10.0)

    holder = threading.Thread(target=hold_window)
    holder.start()
    assert window_held.wait(2.0)

    done: dict = {}

    def run_ingest():
        with Session(get_engine()) as session:
            service = RagService(
                session,
                embedder=lambda text: [0.0] * 8,
                llm=lambda prompt: "unused",
            )
            target = session.exec(select(Project).where(Project.id == pid)).one()
            done["count"] = service.ingest_files(target)

    worker = threading.Thread(target=run_ingest)
    worker.start()
    # The file is missing on disk, so ingest completes without Ollama — the
    # only thing that can keep it from finishing is the held window.
    import time

    time.sleep(0.3)
    assert not done, "ingest_files ran through a held maintenance window"
    release.set()
    holder.join(10.0)
    worker.join(10.0)
    assert done["count"] == 0
    with Session(get_engine()) as session:
        row = session.exec(
            select(ProjectFile).where(ProjectFile.project_id == pid)
        ).one()
        assert row.embedding_id == row.id
    _dispose_engine()
