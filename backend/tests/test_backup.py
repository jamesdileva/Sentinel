"""Tests for BackupService (audit A1, v1.17.18.1)."""

import sqlite3
import zipfile
from pathlib import Path

from app.services.backup_service import (
    _add_dir,
    _snapshot_db,
    backups_dir,
    create_backup,
    list_backups,
    prune_backups,
)


def test_backups_dir_is_under_data(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.backup_service.settings",
        type("S", (), {"db_path": tmp_path / "data" / "sqlite" / "sentinel.db"})(),
    )
    result = backups_dir()
    assert result == tmp_path / "data" / "backups"


def test_snapshot_db_creates_file(tmp_path, monkeypatch):
    db_path = tmp_path / "sentinel.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.close()
    monkeypatch.setattr(
        "app.services.backup_service.settings",
        type("S", (), {"db_path": db_path})(),
    )
    dest = tmp_path / "copy.db"
    _snapshot_db(dest)
    assert dest.exists()
    conn2 = sqlite3.connect(str(dest))
    tables = conn2.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn2.close()
    assert any("t" in row[0] for row in tables)


def test_add_dir_empty_dir_returns_zero(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with zipfile.ZipFile(tmp_path / "out.zip", "w") as zf:
        count = _add_dir(zf, empty, "root")
    assert count == 0


def test_add_dir_missing_dir_returns_zero(tmp_path):
    with zipfile.ZipFile(tmp_path / "out.zip", "w") as zf:
        count = _add_dir(zf, tmp_path / "nope", "root")
    assert count == 0


def test_add_dir_with_files(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")
    (src / "b.txt").write_text("world")
    with zipfile.ZipFile(tmp_path / "out.zip", "w") as zf:
        count = _add_dir(zf, src, "data")
    assert count == 2
    with zipfile.ZipFile(tmp_path / "out.zip") as zf:
        names = zf.namelist()
        assert "data/a.txt" in names
        assert "data/b.txt" in names


def test_prune_backups_keeps_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.backup_service.settings",
        type("S", (), {"db_path": tmp_path / "data" / "sqlite" / "sentinel.db"})(),
    )
    bd = backups_dir()
    bd.mkdir(parents=True, exist_ok=True)
    for i in range(5):
        (bd / f"sentinel-{i:06d}.zip").write_text(f"backup {i}")
    removed = prune_backups(keep=2)
    assert removed == 3
    remaining = sorted(bd.glob("sentinel-*.zip"))
    assert len(remaining) == 2


def test_create_backup_basic(tmp_path, monkeypatch):
    """Integration-ish: create a real backup zip with a real SQLite DB."""
    db_path = tmp_path / "sentinel.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test (id INTEGER)")
    conn.close()
    monkeypatch.setattr(
        "app.services.backup_service.settings",
        type(
            "S",
            (),
            {
                "db_path": db_path,
                "chroma_path": tmp_path / "chroma",
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.backup_service.backups_dir",
        lambda: tmp_path / "backups",
    )
    result = create_backup(keep=3)
    assert result["files"] >= 1  # at least the sqlite snapshot
    assert result["skipped"] == []
    target = Path(result["path"])
    assert target.exists()
    assert target.suffix == ".zip"
    with zipfile.ZipFile(target) as zf:
        assert "sqlite/sentinel.db" in zf.namelist()


def test_list_backups_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.backup_service.settings",
        type("S", (), {"db_path": tmp_path / "data" / "sqlite" / "sentinel.db"})(),
    )
    monkeypatch.setattr(
        "app.services.backup_service.backups_dir",
        lambda: tmp_path / "backups",
    )
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)
    assert list_backups() == []
