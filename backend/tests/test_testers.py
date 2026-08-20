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
        "Algo-Trader",
        "Card-Game",
        "Cg",
        "Demake-Engine",
        "Dinner-Menu-Generator",
        "Finsight",
        "Hft-Order-Book",
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


def test_http_retries_unreachable_then_succeeds(tmp_db, project, monkeypatch):
    """v1.17.13.2: dev servers can take ~10 s to bind after launch — retries
    re-attempt unreachable errors; only the successful attempt checkpoints."""
    import httpx as httpx_mod

    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        text = "healthy"

    def flaky(method, url, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx_mod.ConnectError("refused")
        return FakeResp()

    monkeypatch.setattr(httpx_mod, "request", flaky)
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        ctx.http("GET", "http://127.0.0.1:1/x", retries=2, retry_delay_s=0)
        checkpoints = db.exec(
            select(svc.SessionCheckpoint).where(
                svc.SessionCheckpoint.session_id == app_session.id
            )
        ).all()
    assert calls["n"] == 3
    assert len(checkpoints) == 1


def test_http_retries_exhausted_raises(tmp_db, project, monkeypatch):
    import httpx as httpx_mod

    def always_fail(method, url, timeout=None):
        raise httpx_mod.ConnectError("refused")

    monkeypatch.setattr(httpx_mod, "request", always_fail)
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        with pytest.raises(TesterEnvError):
            ctx.http("GET", "http://127.0.0.1:1/x", retries=2, retry_delay_s=0)


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


def test_finsight_run_electron_serves_dashboard(tmp_db, project, monkeypatch):
    """Happy path: the electron shell reaches the Flask backend and GET /
    on :10000 renders the dashboard — no fallback launch (v1.17.17.1)."""
    import httpx as httpx_mod

    launched = []
    monkeypatch.setattr(
        helpers_mod.BuildRunner,
        "_launch_app",
        staticmethod(
            lambda p, cmd, env=None: (launched.append(cmd), "ok")[0] or (True, "ok")
        ),
    )

    class FakeResp:
        status_code = 200
        text = "FinSight"

    monkeypatch.setattr(httpx_mod, "request", lambda *a, **k: FakeResp())
    from app.testers import finsight

    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        finsight.run(TesterContext(project, app_session.id, service))
    assert launched == [finsight.ELECTRON_CMD]


def test_finsight_run_falls_back_to_python_app(tmp_db, project, monkeypatch):
    """If the electron shell cannot reach the backend, the tester launches
    the Flask app directly and still verifies the dashboard (v1.17.17.1)."""
    import httpx as httpx_mod

    launched = []
    monkeypatch.setattr(
        helpers_mod.BuildRunner,
        "_launch_app",
        staticmethod(
            lambda p, cmd, env=None: (launched.append(cmd), "ok")[0] or (True, "ok")
        ),
    )
    monkeypatch.setattr(helpers_mod.time, "sleep", lambda s: None)
    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        text = "FinSight"

    def flaky(method, url, timeout=None):
        calls["n"] += 1
        if calls["n"] <= 7:  # electron launch: all 7 attempts unreachable
            raise httpx_mod.ConnectError("refused")
        return FakeResp()

    monkeypatch.setattr(httpx_mod, "request", flaky)
    from app.testers import finsight

    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        finsight.run(TesterContext(project, app_session.id, service))
    assert launched == [finsight.ELECTRON_CMD, finsight.PYTHON_CMD]
    assert calls["n"] == 8


def test_default_smoke_runs_discovered_test_command(tmp_db, project, monkeypatch):
    """The smoke tester runs the app's discovered `test` command first and
    its output lands in the app log (v1.17.17.1)."""
    from app.services.command_runner import CommandResult
    from app.testers import default_smoke

    project.stack = {
        "language": "python",
        "commands": {"startup": "npm start", "test": "pytest -q"},
    }

    def fake_run(command, cwd=None, timeout=None, env=None):
        return CommandResult(
            command=command,
            exit_code=0,
            stdout="3 passed",
            stderr="",
            duration_seconds=0.1,
        )

    launched = []
    monkeypatch.setattr(
        helpers_mod.BuildRunner,
        "_launch_app",
        staticmethod(
            lambda p, cmd, env=None: (launched.append(cmd), "ok")[0] or (True, "ok")
        ),
    )
    monkeypatch.setattr(helpers_mod, "run_command", fake_run)
    monkeypatch.setattr(helpers_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        svc, "find_project_window", lambda path: (12345, (10, 20, 210, 120))
    )
    monkeypatch.setattr(svc, "_virtual_screen", lambda: (0, 0, 320, 200))
    monkeypatch.setattr(
        svc,
        "capture_window_content",
        lambda hwnd, rect: Image.new("RGB", (200, 100), (9, 8, 7)),
    )
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        default_smoke.run(ctx)
        assert launched == ["npm start"]
        checkpoints = db.exec(
            select(svc.SessionCheckpoint).where(
                svc.SessionCheckpoint.session_id == app_session.id
            )
        ).all()
    labels = [c.label for c in checkpoints]
    assert any(label.startswith("cli pytest -q") for label in labels)
    assert any("app window after launch" in label for label in labels)


def test_default_smoke_red_test_command_fails(tmp_db, project, monkeypatch):
    """A failing discovered test command fails the smoke honestly — the run
    never proceeds to launch (v1.17.17.1)."""
    from app.services.command_runner import CommandResult
    from app.testers import default_smoke

    project.stack = {
        "language": "python",
        "commands": {"startup": "npm start", "test": "pytest -q"},
    }

    def failing_run(command, cwd=None, timeout=None, env=None):
        return CommandResult(
            command=command,
            exit_code=1,
            stdout="FAILED tests/test_app.py",
            stderr="",
            duration_seconds=0.1,
        )

    launched = []
    monkeypatch.setattr(
        helpers_mod.BuildRunner,
        "_launch_app",
        staticmethod(
            lambda p, cmd, env=None: (launched.append(cmd), "ok")[0] or (True, "ok")
        ),
    )
    monkeypatch.setattr(helpers_mod, "run_command", failing_run)
    with DbSession(get_engine()) as db:
        service = AppSessionService(db)
        app_session = service.start(project.id, "t")
        ctx = TesterContext(project, app_session.id, service)
        with pytest.raises(TesterAssertionError):
            default_smoke.run(ctx)
    assert launched == []


def test_screenshot_records_checkpoint_and_file(tmp_db, project, monkeypatch):
    monkeypatch.setattr(
        svc, "find_project_window", lambda path: (12345, (10, 20, 210, 120))
    )
    monkeypatch.setattr(svc, "_virtual_screen", lambda: (0, 0, 320, 200))
    monkeypatch.setattr(
        svc,
        "capture_window_content",
        lambda hwnd, rect: Image.new("RGB", (200, 100), (9, 8, 7)),
    )
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


# ------------------------------------------------- auto-launch / auto-render


def _mk_project_at(db, name, root: Path, startup=""):
    return _mk_project(db, name=name, path=str(root), startup=startup)


def _packaged_app(root: Path, exe_name: str = "WorkFlow Toolkit.exe") -> Path:
    path = root / "release" / "win-unpacked" / exe_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def _fake_launch_recorder():
    calls = []

    def fake_launch(project, cmd, env=None):
        calls.append((project.name, cmd))
        return True, cmd

    return calls, fake_launch


def _window_stub():
    return (12345, (10, 10, 300, 200))


def test_runner_auto_launch_launches_and_captures_window(tmp_db, tmp_path, monkeypatch):
    """v1.17.13.5: a packaged app (release/win-unpacked) is auto-launched
    before the tester runs; when its window appears, a labeled capture is
    registered — no per-tester code."""
    import app.services.app_sessions as svc_mod
    import app.services.tester_runner as runner_mod

    root = tmp_path / "wft"
    _packaged_app(root)
    calls, fake_launch = _fake_launch_recorder()
    monkeypatch.setattr(
        runner_mod.BuildRunner, "_launch_app", staticmethod(fake_launch)
    )
    # the runner's window poll and the capture's window lookup both resolve
    monkeypatch.setattr(runner_mod, "find_project_window", lambda path: _window_stub())
    monkeypatch.setattr(svc_mod, "find_project_window", lambda path: _window_stub())

    class Grabber:
        @staticmethod
        def grab(bbox=None):
            return Image.new("RGB", (320, 200), (10, 20, 30))

    monkeypatch.setattr(svc_mod, "ImageGrab", Grabber)

    tester = Tester(name="Fake wft", description="d", run=_fake_ok, project_slug="x")
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            project = _mk_project_at(db, "demo-app", root, startup="npm start")
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.PASSED
            labels = [
                c.label
                for c in db.exec(
                    select(svc.SessionCheckpoint).where(
                        svc.SessionCheckpoint.session_id == app_session.id
                    )
                ).all()
            ]
            shots = db.exec(
                select(svc.SessionScreenshot).where(
                    svc.SessionScreenshot.session_id == app_session.id
                )
            ).all()
    finally:
        _unregister()
    assert calls == [
        ("demo-app", f'"{root / "release" / "win-unpacked" / "WorkFlow Toolkit.exe"}"')
    ]
    assert "auto-launched packaged app: WorkFlow Toolkit.exe" in labels
    assert "app window after auto-launch" in labels
    # the labeled launch capture + the end-of-session auto-capture
    assert len(shots) == 2


def test_runner_auto_launch_no_window_is_honest_skip(tmp_db, tmp_path, monkeypatch):
    """The app launches but no window appears within the bound — the run
    still passes and records nothing (never a failure)."""
    import app.services.tester_runner as runner_mod

    root = tmp_path / "headless"
    _packaged_app(root, "Headless.exe")
    calls, fake_launch = _fake_launch_recorder()
    monkeypatch.setattr(
        runner_mod.BuildRunner, "_launch_app", staticmethod(fake_launch)
    )
    monkeypatch.setattr(runner_mod, "find_project_window", lambda path: None)
    monkeypatch.setattr(runner_mod, "WINDOW_WAIT_S", 1)

    tester = Tester(
        name="Fake headless", description="d", run=_fake_ok, project_slug="x"
    )
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            project = _mk_project_at(db, "demo-app", root)
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.PASSED
    finally:
        _unregister()
    assert calls == [
        ("demo-app", f'"{root / "release" / "win-unpacked" / "Headless.exe"}"')
    ]


def test_runner_auto_launch_opt_out(tmp_db, tmp_path, monkeypatch):
    import app.services.tester_runner as runner_mod

    root = tmp_path / "optout"
    _packaged_app(root)
    calls, fake_launch = _fake_launch_recorder()
    monkeypatch.setattr(
        runner_mod.BuildRunner, "_launch_app", staticmethod(fake_launch)
    )
    tester = Tester(
        name="Fake optout",
        description="d",
        run=_fake_ok,
        project_slug="x",
        auto_launch=False,
    )
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            project = _mk_project_at(db, "demo-app", root)
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.PASSED
    finally:
        _unregister()
    assert calls == []


def test_runner_auto_launch_failure_is_not_a_failure(tmp_db, tmp_path, monkeypatch):
    import app.services.tester_runner as runner_mod

    root = tmp_path / "fail"
    _packaged_app(root)
    monkeypatch.setattr(
        runner_mod.BuildRunner,
        "_launch_app",
        staticmethod(lambda project, cmd, env=None: (False, "boom")),
    )
    tester = Tester(name="Fake fail", description="d", run=_fake_ok, project_slug="x")
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            project = _mk_project_at(db, "demo-app", root)
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.PASSED
    finally:
        _unregister()


def _fake_render_url(url, tmp_name):
    """Non-blank frame (distinct gray levels > 8) written to tmp_name."""
    from PIL import Image

    image = Image.new("L", (64, 64))
    for x in range(64):
        for y in range(64):
            image.putpixel((x, y), (x + y) % 255)
    image.save(tmp_name, "PNG")


def test_runner_auto_render_web_url_when_no_screenshots(tmp_db, project, monkeypatch):
    """v1.17.13.5: a browser-served tester with web_url that registered no
    screenshots gets one headless render auto-registered."""
    from app.testers import _helpers as helpers_mod

    monkeypatch.setattr(
        helpers_mod, "render_url", lambda url, tmp: _fake_render_url(url, tmp)
    )
    tester = Tester(
        name="Fake browser",
        description="d",
        run=_fake_ok,
        project_slug="x",
        web_url="http://127.0.0.1:5173",
    )
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.PASSED
            labels = [
                c.label
                for c in db.exec(
                    select(svc.SessionCheckpoint).where(
                        svc.SessionCheckpoint.session_id == app_session.id
                    )
                ).all()
            ]
            shots = db.exec(
                select(svc.SessionScreenshot).where(
                    svc.SessionScreenshot.session_id == app_session.id
                )
            ).all()
    finally:
        _unregister()
    assert "headless dashboard render" in labels
    assert len(shots) == 1


def test_runner_auto_render_skips_when_tester_rendered(
    tmp_db, project, tmp_path, monkeypatch
):
    """Testers that register their own frames (card-game, demake) are
    deduped — no second render is forced."""
    from app.testers import _helpers as helpers_mod

    rendered = []
    monkeypatch.setattr(
        helpers_mod,
        "render_url",
        lambda url, tmp: rendered.append(url) or _fake_render_url(url, tmp),
    )
    selfie = tmp_path / "selfie.png"

    def _tester_renders(ctx):
        _fake_render_url("", str(selfie))
        ctx.screenshot_file(str(selfie), "tester's own render")

    tester = Tester(
        name="Fake selfie",
        description="d",
        run=_tester_renders,
        project_slug="x",
        web_url="http://127.0.0.1:5173",
    )
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.PASSED
            shots = db.exec(
                select(svc.SessionScreenshot).where(
                    svc.SessionScreenshot.session_id == app_session.id
                )
            ).all()
    finally:
        _unregister()
    assert len(shots) == 1
    assert rendered == []


def test_runner_auto_render_without_web_url_does_nothing(tmp_db, project, monkeypatch):
    from app.testers import _helpers as helpers_mod

    called = []
    monkeypatch.setattr(
        helpers_mod,
        "render_url",
        lambda url, tmp: called.append(url) or _fake_render_url(url, tmp),
    )
    tester = Tester(
        name="Fake desktop", description="d", run=_fake_ok, project_slug="x"
    )
    _register(tester)
    try:
        with DbSession(get_engine()) as db:
            app_session = TesterRunner(db).run(project)
            db.refresh(app_session)
            assert app_session.status == SessionStatus.PASSED
    finally:
        _unregister()
    assert called == []
