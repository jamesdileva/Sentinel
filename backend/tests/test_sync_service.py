"""Sprint 12.1 + 15: GitHub-backed repo sync service tests.

The GitHub API is mocked with httpx.MockTransport and git operations are
replaced via monkeypatched `run_command`, so no network or git tooling is ever
touched. Re-indexing is a no-op stub. (docs/01 Rule 6: every feature is tested.)
"""

from pathlib import Path

import httpx
import pytest

from app.services import sync_service
from app.services.sync_service import (
    RepoSyncService,
    latest_sync_run,
    queue_knowledge_index_unembedded,
    run_sync,
)


@pytest.fixture(autouse=True)
def _no_persist(monkeypatch):
    """Tests record run outcomes in the DB; keep the real DB untouched except
    for the dedicated persistence test (which uses tmp_db explicitly)."""
    real = sync_service.persist_sync_run
    monkeypatch.setattr(sync_service, "persist_sync_run", lambda **kwargs: None)
    monkeypatch.setattr(sync_service, "_real_persist_sync_run", real, raising=False)


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


def _fake_result(exit_code=0, stderr="", stdout=""):
    from types import SimpleNamespace

    return SimpleNamespace(exit_code=exit_code, stderr=stderr, stdout=stdout)


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
    # only the clone run happens: no checkout exists, so no HEAD reads
    assert len(calls) == 1
    command = calls[0]
    assert command.startswith("git clone")
    assert "https://github.com/jamesdileva/MyApp.git" in command
    assert "jamesdileva/MyApp" in command
    # a fresh clone is always "changed" -> reindex runs over its dir
    assert result["indexed"] == 1


def test_sync_pulls_existing_repo(tmp_path, monkeypatch):
    (tmp_path / "jamesdileva").mkdir()
    checkout = tmp_path / "jamesdileva" / "MyApp"
    checkout.mkdir()
    (checkout / ".git").mkdir()
    calls: list[tuple] = []

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
    pull_call = [c for c in calls if c[0] == "git pull --ff-only"]
    assert pull_call and "jamesdileva" in pull_call[0][1] and "MyApp" in pull_call[0][1]


def test_sync_skips_reindex_when_head_unchanged(tmp_path, monkeypatch):
    """Sprint 15: a pull that did not move HEAD triggers no reindex and no
    knowledge queueing — the expensive steps are skipped entirely."""
    (tmp_path / "jamesdileva").mkdir()
    checkout = tmp_path / "jamesdileva" / "MyApp"
    checkout.mkdir()
    (checkout / ".git").mkdir()
    calls: list[str] = []
    reindex_calls: list[list[str]] = []

    def fake_run(command, cwd=None, timeout=None, env=None):
        calls.append(command)
        return _fake_result()

    monkeypatch.setattr(sync_service, "run_command", fake_run)
    monkeypatch.setattr(
        sync_service.IndexerService,
        "scan_all_projects",
        lambda self, watch_dirs=None: reindex_calls.append(watch_dirs) or [1],
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
    assert result["indexed"] == 0
    assert reindex_calls == []
    assert result["knowledge"] == {"queued": 0, "skipped": "no-changes"}


def test_sync_reindexes_only_changed_repo(tmp_path, monkeypatch):
    """One repo pulled with a moved HEAD, another pulled with none: only the
    moved repo's directory is passed to the indexer (Sprint 15)."""
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "moved").mkdir()
    (tmp_path / "a" / "moved" / ".git").mkdir()
    (tmp_path / "a" / "quiet").mkdir()
    (tmp_path / "a" / "quiet" / ".git").mkdir()
    counts: dict[str, int] = {}

    def fake_run(command, cwd=None, timeout=None, env=None):
        if command == "git rev-parse --short HEAD":
            base = Path(cwd).name
            count = counts.get(base, 0)
            counts[base] = count + 1
            sha = "shasta-new" if (base == "moved" and count >= 1) else "shasta-old"
            return _fake_result(stdout=sha)
        return _fake_result()

    monkeypatch.setattr(sync_service, "run_command", fake_run)
    scan_dirs: list[list[str]] = []
    monkeypatch.setattr(
        sync_service.IndexerService,
        "scan_all_projects",
        lambda self, watch_dirs=None: scan_dirs.append(watch_dirs) or [],
    )
    client = _service(
        str(tmp_path),
        [
            {"full_name": "a/moved", "clone_url": "https://github.com/a/moved.git"},
            {"full_name": "a/quiet", "clone_url": "https://github.com/a/quiet.git"},
        ],
    )
    result = client.sync()
    assert result["indexed"] == 0
    assert scan_dirs == [[f"{tmp_path}/a/moved"]]


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


def test_persist_sync_run_and_latest(tmp_db, monkeypatch):
    """Sprint 15: a completed sync persists its outcome; latest_sync_run
    returns the newest row for the dashboard pill and /system/sync."""
    import time

    from sqlmodel import Session

    from app.db.connection import get_engine

    monkeypatch.setattr(
        sync_service, "persist_sync_run", sync_service._real_persist_sync_run
    )
    sync_service.persist_sync_run(status="skipped", detail="token not configured")
    time.sleep(0.01)  # distinct ran_at: SQLite stores µs precision
    sync_service.persist_sync_run(
        status="success",
        cloned=["a/b"],
        pulled=["c/d"],
        failed={"e/f": "pull failed: x"},
        indexed=2,
        knowledge_queued=1,
    )
    with Session(get_engine()) as session:
        report = latest_sync_run(session)
    assert report["status"] == "success"
    with Session(get_engine()) as session:
        report = latest_sync_run(session)
    assert report["status"] == "success"
    assert report["cloned"] == ["a/b"]
    assert report["pulled"] == ["c/d"]
    assert report["failed"] == {"e/f": "pull failed: x"}
    assert report["indexed"] == 2
    assert report["knowledge_queued"] == 1


def test_latest_sync_run_returns_none_when_never_synced(tmp_db):
    from sqlmodel import Session

    from app.db.connection import get_engine

    with Session(get_engine()) as session:
        assert latest_sync_run(session) is None


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


# ── knowledge auto-index after sync (Sprint 12.2) ─────────────────────


def test_sync_queues_knowledge_for_unembedded_projects(tmp_path, tmp_db, monkeypatch):
    """After a successful sync, projects under *changed* repos whose files are
    not yet embedded get a RAG index task queued (the Knowledge tab then fills
    on its own). Sprint 15: unchanged repos are never considered."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.db.models import Project, ProjectFile

    with Session(get_engine()) as session:
        session.add(
            Project(
                id="p1",
                name="Alpha",
                path=f"{tmp_path}/a/b",
                language="python",
            )
        )
        session.add(
            ProjectFile(
                project_id="p1", path="main.py", id="f1", absolute_path="main.py"
            )
        )
        session.add(
            ProjectFile(
                project_id="p1",
                path="embedded.py",
                id="f2",
                embedding_id="f2",
                absolute_path="embedded.py",
            )
        )
        session.commit()

    queued: list[str] = []

    def fake_submit(name, args=None, task_id=None):
        queued.append(args[0])

    from app.services.job_scheduler import scheduler as job_scheduler

    monkeypatch.setattr(job_scheduler, "submit", fake_submit)
    monkeypatch.setattr(sync_service, "run_command", lambda *a, **k: _fake_result())
    monkeypatch.setattr(
        sync_service.IndexerService,
        "scan_all_projects",
        lambda self, watch_dirs=None: [1],
    )
    monkeypatch.setattr(sync_service.OllamaService, "is_available", lambda self: True)
    client = _service(
        str(tmp_path),
        [{"full_name": "a/b", "clone_url": "https://github.com/a/b.git"}],
    )
    result = client.sync()
    assert result["knowledge"] == {"queued": 1, "skipped": None}
    assert queued == ["p1"]  # only the project with at least one unembedded file


def test_sync_skips_knowledge_when_ollama_unavailable(tmp_path, tmp_db, monkeypatch):
    """No knowledge tasks are queued when Ollama cannot be reached: the sync
    itself must still succeed (best-effort, rule: never fail the sync)."""
    monkeypatch.setattr(sync_service.OllamaService, "is_available", lambda self: False)
    monkeypatch.setattr(sync_service, "run_command", lambda *a, **k: _fake_result())
    monkeypatch.setattr(
        sync_service.IndexerService,
        "scan_all_projects",
        lambda self, watch_dirs=None: [1],
    )
    client = _service(
        str(tmp_path),
        [{"full_name": "a/b", "clone_url": "https://github.com/a/b.git"}],
    )
    result = client.sync()
    assert result["knowledge"] == {"queued": 0, "skipped": "ollama-unavailable"}


# ── v1.17: startup auto knowledge-index (config-gated) ────────────────


def test_auto_index_queues_all_unembedded(tmp_db, monkeypatch):
    """`queue_knowledge_index_unembedded()` with no path filter targets every
    project with unembedded files — used by the startup scan (v1.17)."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.db.models import Project, ProjectFile

    with Session(get_engine()) as session:
        session.add(
            Project(
                id="p1",
                name="Alpha",
                path="C:/watch/a",
                language="python",
            )
        )
        session.add(
            ProjectFile(
                project_id="p1", path="main.py", id="f1", absolute_path="main.py"
            )
        )
        session.add(
            Project(
                id="p2",
                name="Beta",
                path="C:/watch/b",
                language="rust",
            )
        )
        session.add(
            ProjectFile(project_id="p2", path="lib.rs", id="f2", absolute_path="lib.rs")
        )
        session.commit()

    queued: list[str] = []

    def fake_submit(name, args=None, task_id=None):
        queued.append(args[0])

    from app.services.job_scheduler import scheduler as job_scheduler

    monkeypatch.setattr(job_scheduler, "submit", fake_submit)
    monkeypatch.setattr(sync_service.OllamaService, "is_available", lambda self: True)

    result = queue_knowledge_index_unembedded()
    assert result == {"queued": 2, "skipped": None}
    assert sorted(queued) == ["p1", "p2"]


def test_auto_index_empty_paths_window_is_noop():
    """An explicit empty path window must not queue anything (normalized
    'no-changes' behaviour of the sync path)."""
    assert queue_knowledge_index_unembedded(paths=[]) == {
        "queued": 0,
        "skipped": "no-changes",
    }


def test_auto_index_path_filter_restricts_projects(tmp_db, monkeypatch):
    """The sync pass passes the changed repos' paths; projects outside that
    window must never be touched (their embeddings are already current)."""
    from sqlmodel import Session

    from app.db.connection import get_engine
    from app.db.models import Project, ProjectFile

    with Session(get_engine()) as session:
        session.add(
            Project(id="p1", name="Alpha", path="C:/watch/a", language="python")
        )
        session.add(
            ProjectFile(
                project_id="p1", path="main.py", id="f1", absolute_path="main.py"
            )
        )
        session.add(Project(id="p2", name="Beta", path="C:/other/x", language="python"))
        session.add(
            ProjectFile(project_id="p2", path="x.py", id="f2", absolute_path="x.py")
        )
        session.commit()

    queued: list[str] = []

    def fake_submit(name, args=None, task_id=None):
        queued.append(args[0])

    from app.services.job_scheduler import scheduler as job_scheduler

    monkeypatch.setattr(job_scheduler, "submit", fake_submit)
    monkeypatch.setattr(sync_service.OllamaService, "is_available", lambda self: True)

    result = queue_knowledge_index_unembedded(paths=["C:/watch/a"])
    assert result == {"queued": 1, "skipped": None}
    assert queued == ["p1"]
