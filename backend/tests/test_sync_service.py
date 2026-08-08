"""Sprint 12.1: GitHub-backed repo sync service tests.

The GitHub API is mocked with httpx.MockTransport and git operations are
replaced via monkeypatched `run_command`, so no network or git tooling is ever
touched. Re-indexing is a no-op stub. (docs/01 Rule 6: every feature is tested.)
"""

import httpx
import pytest

from app.services import sync_service
from app.services.sync_service import RepoSyncService, run_sync


def _api_handler(repos: list[dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer test-token"
        assert request.headers.get("Accept") == "application/vnd.github+json"
        if request.url.path == "/user/repos":
            return httpx.Response(200, json=repos)
        return httpx.Response(500, json={})

    return httpx.MockTransport(handler)


def _service(root: str, repos: list[dict]) -> RepoSyncService:
    return RepoSyncService(token="test-token", root=root, transport=_api_handler(repos))


def _fake_result(exit_code=0, stderr=""):
    from types import SimpleNamespace

    return SimpleNamespace(exit_code=exit_code, stderr=stderr, stdout="")


def test_remote_repos_lists_and_paginates():
    client = _service(
        "C:\\projects", [{"full_name": "a/b", "clone_url": "https://github.com/a/b"}]
    )
    assert client.remote_repos() == [
        {"full_name": "a/b", "url": "https://github.com/a/b"}
    ]


def test_not_configured_raises(tmp_path):
    client = RepoSyncService(token="", root=str(tmp_path))
    assert client.configured is False
    with pytest.raises(ValueError):
        client.sync()


def test_sync_clones_missing_repo(tmp_path, monkeypatch):
    calls: list[str] = []

    def fake_run(command, cwd=None, timeout=None, env=None):
        calls.append(command)
        return _fake_result()

    monkeypatch.setattr(sync_service, "run_command", fake_run)
    monkeypatch.setattr(
        sync_service.IndexerService,
        "scan_all_projects",
        lambda self, watch_dirs=None: [1],
    )
    client = _service(
        str(tmp_path),
        [
            {
                "full_name": "jamesdileva/MyApp",
                "clone_url": "https://github.com/jamesdileva/MyApp.git",
            }
        ],
    )
    result = client.sync()
    assert result["cloned"] == ["jamesdileva/MyApp"]
    assert result["pulled"] == []
    assert len(calls) == 1
    command = calls[0]
    assert command.startswith("git clone")
    assert "https://github.com/jamesdileva/MyApp.git" in command
    assert "jamesdileva/MyApp" in command


def test_sync_pulls_existing_repo(tmp_path, monkeypatch):
    (tmp_path / "jamesdileva").mkdir()
    checkout = tmp_path / "jamesdileva" / "MyApp"
    checkout.mkdir()
    (checkout / ".git").mkdir()
    calls: list[str] = []

    def fake_run(command, cwd=None, timeout=None, env=None):
        calls.append((command, cwd))
        return _fake_result()

    monkeypatch.setattr(sync_service, "run_command", fake_run)
    monkeypatch.setattr(
        sync_service.IndexerService,
        "scan_all_projects",
        lambda self, watch_dirs=None: [1],
    )
    client = _service(
        str(tmp_path),
        [
            {
                "full_name": "jamesdileva/MyApp",
                "clone_url": "https://github.com/jamesdileva/MyApp.git",
            }
        ],
    )
    result = client.sync()
    assert result["pulled"] == ["jamesdileva/MyApp"]
    assert "jamesdileva" in calls[0][1] and "MyApp" in calls[0][1]


def test_sync_records_failed_repo(tmp_path, monkeypatch):
    def fake_run(command, cwd=None, timeout=None, env=None):
        return _fake_result(exit_code=128, stderr="fatal: could not read")

    monkeypatch.setattr(sync_service, "run_command", fake_run)
    monkeypatch.setattr(
        sync_service.IndexerService,
        "scan_all_projects",
        lambda self, watch_dirs=None: [],
    )
    client = _service(
        str(tmp_path),
        [{"full_name": "a/b", "clone_url": "https://github.com/a/b.git"}],
    )
    result = client.sync()
    assert result["failed"] == {"a/b": "clone failed: fatal: could not read"}


def test_run_sync_skips_when_unconfigured(monkeypatch):
    monkeypatch.setattr(sync_service.settings, "github_token", "")
    result = run_sync()
    assert result == {"configured": False, "skipped": True}


def test_run_sync_returns_github_error(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_service.settings, "github_token", "test-token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    client = RepoSyncService(
        token="test-token", root=str(tmp_path), transport=httpx.MockTransport(handler)
    )
    result = run_sync(client)
    assert result["configured"] is True
    assert result["error"].startswith("HTTPStatusError")
