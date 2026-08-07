"""Startup validation checks (Sprint 12)."""

from app.services.startup_check import (
    ComponentStatus,
    _check_chroma,
    _check_watch_dirs,
)


def test_watch_dirs_missing_reported():
    from app.core.config import settings

    settings.watch_dirs = ["Z:/nonexistent/sentinel-does-not-exist"]
    status = _check_watch_dirs()
    assert status.ok is False
    assert "Missing" in status.detail


def test_watch_dirs_empty_reported():
    from app.core.config import settings

    settings.watch_dirs = []
    status = _check_watch_dirs()
    assert status.ok is False
    assert "No watch directories" in status.detail


def test_chroma_path_created(tmp_path):
    target = tmp_path / "chroma"
    status = _check_chroma(target)
    assert status.ok is True
    assert target.exists()


def test_chroma_non_directory_reported(tmp_path):
    target = tmp_path / "file"
    target.write_text("not a dir", encoding="utf-8")
    status = _check_chroma(target)
    assert status.ok is False


def test_component_status_fields():
    status = ComponentStatus("database", True, "ok")
    assert status.name == "database"
    assert status.ok is True
    assert status.detail == "ok"
