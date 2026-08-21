"""Sprint 11: Celery task coverage (app/tasks/*).

Tasks are invoked directly (not via the broker); the service seams are faked
per task so tests stay deterministic and hermetic. All run against tmp_db.
"""

from sqlmodel import Session

from app.db.connection import get_engine
from app.db.models import BuildLog, Project
from app.tasks import build_tasks, rag_tasks, sync_tasks, world_sim_tasks


class FakeLog:
    def __init__(self, id, success=True, exit_code=0):
        self.id = id
        self.success = success
        self.exit_code = exit_code
        self.launch_command = None
        self.commands = {}


class FakeProject:
    id = "p-fake"
    name = "Fake"


def _seed_project(tmp_db, project_id: str = "p-fake", name: str = "Fake") -> Project:
    with Session(get_engine()) as session:
        project = Project(
            id=project_id, name=name, path="does/not/exist", language="python"
        )
        session.add(project)
        session.commit()
        return project


# --- world_sim_tasks ----------------------------------------------------------


def test_world_sim_tick(tmp_db, monkeypatch):
    class FakeService:
        def catch_up(self):
            return 2

    monkeypatch.setattr(world_sim_tasks, "WorldSimulatorService", lambda: FakeService())
    assert world_sim_tasks.world_sim_tick() == {"days_advanced": 2}


# --- rag_tasks -----------------------------------------------------------------


def test_run_index_knowledge(tmp_db, monkeypatch):
    class FakeRag:
        def __init__(self, session):
            self.session = session

        @staticmethod
        def get_project(session, project_id):
            return FakeProject()

        def index_project(self, project, with_summary=False, progress=None):
            if progress:
                progress(3, 3)
            return {"files": 3, "commits": 1}

        def close(self):
            pass

    monkeypatch.setattr(rag_tasks, "RagService", FakeRag)
    result = rag_tasks.run_index_knowledge("p-fake")
    assert result == {"project_id": "p-fake", "counts": {"files": 3, "commits": 1}}


# --- sync_tasks ----------------------------------------------------------------


def test_run_repo_sync_unconfigured_publishes_reason(tmp_db, monkeypatch):
    """v1.17.1: an unconfigured sync must say *why* on the live feed — the
    old 'nothing changed' message disguised the missing token."""
    published: list[dict] = []
    monkeypatch.setattr(
        sync_tasks, "run_sync", lambda: {"configured": False, "skipped": True}
    )
    monkeypatch.setattr(
        sync_tasks.activity_bus,
        "publish_event",
        lambda *a, **kw: published.append({"args": a, "kwargs": kw}),
    )
    result = sync_tasks.run_repo_sync()
    assert result["skipped"] is True
    assert len(published) == 1
    assert published[0]["args"][0] == "sync"
    assert "not configured" in published[0]["args"][1]


def test_run_repo_sync_nothing_changed_has_detail(tmp_db, monkeypatch):
    published: list[dict] = []
    monkeypatch.setattr(
        sync_tasks,
        "run_sync",
        lambda: {"configured": True, "cloned": [], "pulled": [], "failed": {}},
    )
    monkeypatch.setattr(
        sync_tasks.activity_bus,
        "publish_event",
        lambda *a, **kw: published.append({"args": a, "kwargs": kw}),
    )
    sync_tasks.run_repo_sync()
    assert published[0]["args"][0] == "sync"
    assert "nothing changed" in published[0]["args"][1]
    assert published[0]["kwargs"]["detail"]


def test_repo_sync_no_longer_chains_security_scan_all(tmp_db, monkeypatch):
    """v1.17.7: the security scan-all runs on its own beat — the repo-sync
    task must not trigger scans, even when configured (avoids double scans
    on the daily schedule)."""
    calls: list[str] = []
    monkeypatch.setattr(
        sync_tasks,
        "run_sync",
        lambda: {"configured": True, "cloned": [], "pulled": [], "failed": {}},
    )
    monkeypatch.setattr(
        build_tasks, "run_security_scan_all", lambda: calls.append("scan") or {}
    )
    sync_tasks.run_repo_sync()
    assert calls == []  # scan-all owns the scan schedule now

    monkeypatch.setattr(
        sync_tasks, "run_sync", lambda: {"configured": False, "skipped": True}
    )
    calls.clear()
    sync_tasks.run_repo_sync()
    assert calls == []  # tokenless sync says its piece; still no scan here


# --- build_tasks ----------------------------------------------------------------


def test_run_build_task_with_existing_log(tmp_db, monkeypatch):
    _seed_project(tmp_db)
    with Session(get_engine()) as session:
        log = BuildLog(id="log-1", project_id="p-fake", success=True)
        session.add(log)
        session.commit()

    class FakeRunner:
        def __init__(self, session):
            self.session = session

        @staticmethod
        def get_project(session, project_id):
            return FakeProject()

        def run_build(self, project, log=None):
            return FakeLog(log.id)

    monkeypatch.setattr(build_tasks, "BuildRunner", FakeRunner)
    result = build_tasks.run_build_task("p-fake", "log-1")
    assert result == {
        "job_id": "log-1",
        "project_id": "p-fake",
        "success": True,
        "exit_code": 0,
        "launch_command": None,
    }


def test_run_build_task_creates_missing_log(tmp_db, monkeypatch):
    _seed_project(tmp_db)

    class FakeRunner:
        def __init__(self, session):
            self.session = session

        @staticmethod
        def get_project(session, project_id):
            return FakeProject()

        def run_build(self, project, log=None):
            return FakeLog(log.id, success=False, exit_code=1)

    monkeypatch.setattr(build_tasks, "BuildRunner", FakeRunner)
    result = build_tasks.run_build_task("p-fake", "log-9")
    assert result["job_id"] == "log-9"
    assert result["success"] is False
    assert result["exit_code"] == 1


def test_run_tests_task(tmp_db, monkeypatch):
    _seed_project(tmp_db)

    class FakeResult:
        id = "tr-1"
        passed = 3
        failed = 0
        summary = "3 passed"

    class FakeRunner:
        def __init__(self, session):
            self.session = session

        @staticmethod
        def get_project(session, project_id):
            return FakeProject()

        def run_tests(self, project):
            return FakeResult()

    monkeypatch.setattr(build_tasks, "TestRunner", FakeRunner)
    result = build_tasks.run_tests_task("p-fake")
    assert result == {
        "job_id": "tr-1",
        "project_id": "p-fake",
        "passed": 3,
        "failed": 0,
        "summary": "3 passed",
    }


def test_run_security_scan_task(tmp_db, monkeypatch):
    _seed_project(tmp_db)

    class FakeScanner:
        def __init__(self, session):
            self.session = session

        @staticmethod
        def get_project(session, project_id):
            return FakeProject()

        def scan_project(self, project):
            return ["f1", "f2"]

    monkeypatch.setattr(build_tasks, "SecurityScanner", FakeScanner)
    result = build_tasks.run_security_scan_task("p-fake")
    assert result == {"project_id": "p-fake", "count": 2}


def test_run_security_scan_all(tmp_db, monkeypatch):
    _seed_project(tmp_db, project_id="p-1", name="One")
    _seed_project(tmp_db, project_id="p-2", name="Two")

    class FakeRepo:
        def __init__(self, session):
            self.session = session

        def list(self, limit=1000):
            return [FakeProject() for _ in range(2)]

    monkeypatch.setattr("app.repositories.ProjectRepository", FakeRepo)
    monkeypatch.setattr(
        build_tasks,
        "run_security_scan_task",
        lambda p_id: {"project_id": p_id, "count": 1},
    )
    result = build_tasks.run_security_scan_all()
    assert result == {"projects_scanned": 2}
