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


def test_remote_ollama_host_fails_the_startup_check(monkeypatch):
    """A5: a non-loopback host with no opt-in fails the check *before* any
    request is made, so nothing is ever sent off the machine."""
    from app.core.config import settings
    from app.services.startup_check import _check_ollama

    monkeypatch.setattr(settings, "ollama_host", "http://192.168.1.50:11434")
    monkeypatch.setattr(settings, "allow_remote_ollama", False)
    status = _check_ollama()
    assert status.ok is False
    assert "not loopback" in status.detail
    assert "SENTINEL_ALLOW_REMOTE_OLLAMA" in status.detail


def test_opted_in_remote_host_passes_the_host_check(monkeypatch):
    """With the opt-in the gate opens (the later probe may still fail — that
    is a reachability question, not a Rule 1 one)."""
    from app.core.config import settings
    from app.services import startup_check

    monkeypatch.setattr(settings, "ollama_host", "http://192.168.1.50:11434")
    monkeypatch.setattr(settings, "allow_remote_ollama", True)
    monkeypatch.setattr(
        startup_check.OllamaService, "list_models", lambda self: ["llama3.1:8b"]
    )
    status = startup_check._check_ollama()
    assert status.ok is True
