"""Scripted tester tests (later.md Tier 2, docs/tier2_plan.md).

Covers: registry resolution (custom -> default smoke -> none), the
TesterContext helpers (http/cli/wait_log/screenshot/launch), the runner's
status mapping (passed/failed/investigate), env redaction, and the API
(descriptor + run). Real subprocess/network work is stubbed; the runner
itself is exercised against a fake tester.
"""

from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest
from PIL import Image
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.core.config import settings
from app.db import connection
from app.db.connection import get_engine
from app.db.models import AppSession, Project, SessionStatus
from app.services import app_sessions as svc
from app.services.app_sessions import AppSessionService
from app.services.tester_runner import TesterRunner
from app.testers import TESTERS, Tester
from app.testers import _helpers as helpers_mod
from app.testers._helpers import (
    TesterAssertionError,
    TesterContext,
    TesterEnvError,
    TesterTimeoutError,
)


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", tmp_path / "data" / "sqlite" / "test.db")
    _dispose_engine()
    connection.init_db()
    yield tmp_path / "data" / "sqlite" / "test.db"
    _dispose_engine()


def _dispose_engine() -> None:
    engine = connection._engine
    connection._engine = None
    if engine is not None:
        engine.dispose()


def _mk_project(db, name="demo-app", path=None, startup="") -> Project:
    project = Project(
        name=name,
        path=path or f"C:\\projects\\{name}",
        repo_url="",
        language="python",
    )
    if startup:
        project.stack = {"language": "python", "commands": {"startup": startup}}
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@pytest.fixture(autouse=True)
def _fake_grabber(monkeypatch):
    image = Image.new("RGB", (320, 200), (10, 20, 30))

    class Grabber:
        @staticmethod
        def grab():
            return image.copy()

    monkeypatch.setattr(svc, "ImageGrab", Grabber)
    # Hermetic: never resolve real windows on the host machine.
    monkeypatch.setattr(svc, "find_project_window", lambda path: None)


def _log_path(project_name: str) -> Path:
    return (
        Path(settings.db_path).parent.parent
        / "logs"
        / "apps"
        / f"{svc._slug(project_name)}.log"
    )


@pytest.fixture()
def project(tmp_db):
    with DbSession(get_engine()) as db:
        return _mk_project(db)


def _register(tester) -> None:
    """Register a fake tester under the demo-app slug; returns a cleanup."""
    TESTERS["demo-app"] = tester


def _unregister() -> None:
    TESTERS.pop("demo-app", None)


# ------------------------------------------------------------------- registry


def test_registry_has_phase_a_testers():
    assert set(TESTERS) == {
        "Ag",
        "Card-Game",
        "Cg",
        "Demake-Engine",
        "Dinner-Menu-Generator",
        "Tv-Scheduler",
        "Workflow-Toolkit",
    }


def test_resolve_custom_tester_wins_over_smoke(tmp_db):
    with DbSession(get_engine()) as db:
        project = _mk_project(db, name="Cg", startup="npm start")
        tester = TesterRunner(db).resolve(project)
    assert tester.name == "CG backend + Electron"


def test_resolve_default_smoke_for_launchable(tmp_db):
    with DbSession(get_engine()) as db:
        project = _mk_project(db, name="Some App", startup="npm start")
        tester = TesterRunner(db).resolve(project)
    assert tester.kind == "default-smoke"


def test_resolve_none_without_startup(tmp_db):
    with DbSession(get_engine()) as db:
        project = _mk_project(db, name="Some App", startup="")
        assert TesterRunner(db).resolve(project) is None
        assert TesterRunner(db).describe(project) is None


# --------------------------------------------------------------- TesterContext


class _FakeHttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — stdlib method name
        body = b"healthy"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence the dev server chatter
        pass


@pytest.fixture()
def http_server():
    import threading
    from http.server import ThreadingHTTPServer

    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeHttpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_http_success_and_assert(tmp_db, project, http_server):
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        ctx.http("GET", f"{http_server}/health", expect_body="healthy")
        with pytest.raises(TesterAssertionError):
            ctx.http("GET", f"{http_server}/health", expect=404)
        with pytest.raises(TesterAssertionError):
            ctx.http("GET", f"{http_server}/health", expect_body="nope")
        # dead port -> env error
        with pytest.raises(TesterEnvError):
            ctx.http("GET", "http://127.0.0.1:9/health", timeout_s=2)


def test_cli_appends_output_and_checks(tmp_db, project, monkeypatch):
    from app.services.command_runner import CommandResult

    def fake_run(command, cwd=None, timeout=None, env=None):
        return CommandResult(
            command=command,
            exit_code=0,
            stdout="ok marker here",
            stderr="",
            duration_seconds=0.1,
        )

    monkeypatch.setattr(helpers_mod, "run_command", fake_run)
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        ctx.cli("probe --flag", expect_stdout="marker")
        lines = _log_path(project.name).read_text(encoding="utf-8").splitlines()
    assert any("[tester] $ probe --flag" in line for line in lines)
    assert any("ok marker here" in line for line in lines)


def test_cli_never_logs_env_values(tmp_db, project, monkeypatch):
    from app.services.command_runner import CommandResult

    def fake_run(command, cwd=None, timeout=None, env=None):
        return CommandResult(
            command=command,
            exit_code=0,
            stdout="output",
            stderr="",
            duration_seconds=0.1,
        )

    monkeypatch.setattr(helpers_mod, "run_command", fake_run)
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        ctx.cli("probe", env={"SECRET_VALUE": "hunter2"})
        log = _log_path(project.name).read_text(encoding="utf-8")
    assert "hunter2" not in log
    assert "SECRET_VALUE" not in log


def test_cli_bad_exit_raises_assertion(tmp_db, project, monkeypatch):
    from app.services.command_runner import CommandResult

    monkeypatch.setattr(
        helpers_mod,
        "run_command",
        lambda *a, **k: CommandResult("x", 1, "", "boom", 0.1),
    )
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        with pytest.raises(TesterAssertionError):
            ctx.cli("probe", expect_exit=0)


def test_cli_timeout_raises_timeout(tmp_db, project, monkeypatch):
    from app.services.command_runner import CommandResult

    monkeypatch.setattr(
        helpers_mod,
        "run_command",
        lambda *a, **k: CommandResult("x", -1, "", "", 30, timed_out=True),
    )
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        with pytest.raises(TesterTimeoutError):
            ctx.cli("probe", timeout_s=30)


def test_wait_log_sees_pattern_then_times_out(tmp_db, project):
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)

        def append_line(text):
            path = _log_path(project.name)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"{text}\n")

        ctx.mark_log()
        append_line("hello world")
        ctx.wait_log("hello", timeout_s=5)
        with pytest.raises(TesterTimeoutError):
            ctx.wait_log("never-seen", timeout_s=1)


def test_launch_failure_is_env_error(tmp_db, project, monkeypatch):
    monkeypatch.setattr(
        helpers_mod.BuildRunner,
        "_launch_app",
        staticmethod(lambda project, cmd, env=None: (False, "port taken")),
    )
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        with pytest.raises(TesterEnvError):
            ctx.launch("probe")


def test_screenshot_records_checkpoint_and_file(tmp_db, project):
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        ctx.screenshot("window")
        shots = db.exec(
            select(svc.SessionScreenshot).where(
                svc.SessionScreenshot.session_id == app_session.id
            )
        ).all()
        checkpoints = db.exec(
            select(svc.SessionCheckpoint).where(
                svc.SessionCheckpoint.session_id == app_session.id
            )
        ).all()
    assert len(shots) == 1
    assert len(checkpoints) == 1
    assert shots[0].checkpoint_id == checkpoints[0].id


# ---------------------------------------------------------------------- runner


def _fake_ok(ctx):
    pass  # zero steps, zero asserts -> passed


def test_runner_passed_status(tmp_db, project):
    tester = Tester(name="Fake ok", description="d", run=_fake_ok, project_slug="x")
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.PASSED
            assert app_session.title == "Tester: Fake ok"
            assert "0 step(s)" in app_session.actual_outcome
            assert app_session.log_slice
        lines = _log_path(project.name).read_text(encoding="utf-8").splitlines()
        assert lines[-1].endswith(": passed")
    finally:
        _unregister()


def _fake_assert(ctx):
    raise TesterAssertionError("expected 'x' in body")


def test_runner_failed_status(tmp_db, project):
    tester = Tester(
        name="Fake bad", description="d", run=_fake_assert, project_slug="x"
    )
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.FAILED
            assert app_session.actual_outcome == "expected 'x' in body"
    finally:
        _unregister()


def _fake_env(ctx):
    raise TesterEnvError("port 8000 taken")


def test_runner_investigate_status(tmp_db, project):
    tester = Tester(name="Fake env", description="d", run=_fake_env, project_slug="x")
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.INVESTIGATE
    finally:
        _unregister()


def _fake_crash(ctx):
    raise RuntimeError("boom")


def test_runner_crash_is_failed_not_exception(tmp_db, project):
    tester = Tester(
        name="Fake crash", description="d", run=_fake_crash, project_slug="x"
    )
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.FAILED
            assert "Tester crashed" in app_session.actual_outcome
    finally:
        _unregister()


def test_runner_no_tester_raises(tmp_db, project):
    with DbSession(get_engine()) as db:
        with pytest.raises(Exception):
            TesterRunner(db).run(project)


# ------------------------------------------------------------------------ API


def test_api_descriptor_and_run(client, project):
    _register(Tester(name="Fake", description="d", run=_fake_ok, project_slug="x"))
    try:
        response = client.get(f"/api/v1/testers/{project.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Fake"
        assert body["kind"] in ("custom", "default-smoke")
    finally:
        _unregister()


def test_api_no_tester_404(client, project):
    response = client.get(f"/api/v1/testers/{project.id}")
    assert response.status_code == 404


def test_api_unknown_project_404(client):
    assert client.get("/api/v1/testers/nope").status_code == 404
    assert (
        client.post("/api/v1/testers/run", json={"project_id": "nope"}).status_code
        == 404
    )


def test_api_run_returns_job_envelope(client, project, monkeypatch):
    from app.services.job_scheduler import scheduler as job_scheduler

    monkeypatch.setattr(job_scheduler, "run_inline", True)
    _register(Tester(name="Fake", description="d", run=_fake_ok, project_slug="x"))
    try:
        response = client.post("/api/v1/testers/run", json={"project_id": project.id})
        assert response.status_code == 202
        body = response.json()
        assert body["job_id"]
        assert body["status"] == "queued"
        with DbSession(get_engine()) as db:
            sessions = db.exec(
                select(AppSession).where(AppSession.project_id == project.id)
            ).all()
        assert len(sessions) == 1
        assert sessions[0].status == SessionStatus.PASSED
    finally:
        _unregister()


# ------------------------------------------------- WorkFlow-Toolkit flagship


def test_workflow_toolkit_tester_registered():
    from app.testers import TESTERS

    tester = TESTERS["Workflow-Toolkit"]
    assert tester.name == "WorkFlow-Toolkit E2E"
    assert tester.kind == "custom"


def test_wft_backend_command_prefers_runtime_python(tmp_path):
    from app.testers import workflow_toolkit as wft

    root = tmp_path / "WorkFlow-Toolkit"
    runtime = root / "backend" / "runtime" / "python" / "python.exe"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("", encoding="utf-8")
    cmd = wft._backend_command(root)
    assert f'"{runtime}"' in cmd
    assert "-m uvicorn app.main:app" in cmd
    assert wft._backend_command(tmp_path / "other") == (
        "cd backend && python -m uvicorn app.main:app"
    )


def test_wft_pytest_command_prefers_runtime_python(tmp_path):
    from app.testers import workflow_toolkit as wft

    root = tmp_path / "WorkFlow-Toolkit"
    runtime = root / "backend" / "runtime" / "python" / "python.exe"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("", encoding="utf-8")
    cmd = wft._pytest_command(root)
    assert f'"{runtime}"' in cmd
    assert "-m pytest tests -q" in cmd
    assert wft._pytest_command(tmp_path / "other") == (
        "cd backend && python -m pytest tests -q"
    )


def test_wft_completed_run_requires_output_report_id(tmp_path, monkeypatch):
    from app.testers import workflow_toolkit as wft
    from app.testers._helpers import TesterAssertionError, TesterContext

    class FakeService:
        def checkpoint(self, *a, **k):
            pass

    ctx = TesterContext(
        type("P", (), {"path": str(tmp_path), "name": "t"})(), "s", FakeService()
    )
    with pytest.raises(TesterAssertionError, match="output_report_id"):
        wft._assert_completed_with_report(ctx, {"status": "Completed"})


def test_wft_pytest_step_neutralizes_inherited_pythonpath(tmp_db, project, monkeypatch):
    from app.services.command_runner import CommandResult
    from app.testers import _helpers
    from app.testers import workflow_toolkit as wft
    from app.testers._helpers import TesterContext

    calls = {}

    def fake_run_command(command, cwd=None, timeout=120, env=None):
        calls["env"] = env
        return CommandResult("", 0, "ok", "", 1.0)

    monkeypatch.setattr(_helpers, "run_command", fake_run_command)
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        ctx.pytest(wft._pytest_command(Path(project.path)), env={"PYTHONPATH": ""})
    assert calls.get("env") == {"PYTHONPATH": ""}


def test_wft_launch_neutralizes_inherited_pythonpath(tmp_db, project, monkeypatch):
    from app.testers import workflow_toolkit as wft
    from app.testers._helpers import BuildRunner, TesterContext

    launched = {}

    def fake_launch(project, cmd, env=None):
        launched["env"] = env
        return True, cmd

    monkeypatch.setattr(BuildRunner, "_launch_app", staticmethod(fake_launch))
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        ctx.launch(wft._backend_command(Path(project.path)), env={"PYTHONPATH": ""})
    assert launched.get("env") == {"PYTHONPATH": ""}
