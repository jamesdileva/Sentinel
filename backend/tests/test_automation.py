"""Sprint 7: build/test/security runner unit tests + API integration."""

import sys
import time
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import connection
from app.db.models import Project, ProjectFile, SecurityFinding
from app.main import app
from app.services.build_runner import BuildRunner
from app.services.command_runner import CommandResult
from app.services.indexer import IndexerService
from app.services.security_scanner import SecurityScanner
from app.services.test_runner import TestRunner as RunnerService

client = TestClient(app)

PYTHON_FIXTURE = "tests/fixtures/sample_python_project"
SCAN_FIXTURE = "tests/fixtures/sample_scan_project"


@pytest.fixture()
def eager(monkeypatch):
    """Run in-process scheduler jobs synchronously so tests need no threads."""
    from app.services.job_scheduler import scheduler

    monkeypatch.setattr(scheduler, "run_inline", True)
    yield
    monkeypatch.setattr(scheduler, "run_inline", False)


def _seed(tmp_db, path: str = PYTHON_FIXTURE) -> str:
    with Session(connection.get_engine()) as session:
        return IndexerService(session).index_project(path).id


def _fake_result(
    exit_code: int = 0, stdout: str = "", stderr: str = ""
) -> CommandResult:
    return CommandResult(
        command="fake",
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.1,
        timed_out=False,
    )


def _project_with_commands(session, commands: dict) -> Project:
    project = Project(
        id="p-build",
        name="Demo",
        path="does/not/exist",
        language="python",
        stack={"commands": commands},
    )
    session.add(project)
    session.commit()
    return project


# --- BuildRunner unit tests ---


def test_build_runner_no_build_command(tmp_db):
    """v1.17.7.5: no discoverable command is NOT a successful build — the
    log records success=None so the UI/feed can say "skipped" instead of
    claiming a pass that never ran anything."""
    with Session(connection.get_engine()) as session:
        project = _project_with_commands(session, {})
        log = BuildRunner(session).run_build(project)
        assert log.success is None
        assert log.exit_code is None
        assert log.completed_at is not None
        assert log.commands.get("build") == ""
        assert "No build command" in (log.stdout or "")


def test_build_runner_stale_empty_stack_rediscovers(tmp_db, tmp_path):
    """v1.17.7.6: a repo indexed before CMake discovery existed has a stored
    stack with an empty build command — the runner must re-discover instead
    of skipping, so `cmake --build build` runs for C++ projects."""
    root = tmp_path / "cmake-project"
    root.mkdir()
    (root / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.15)\n", encoding="utf-8"
    )
    with Session(connection.get_engine()) as session:
        project = _project_with_commands(session, {})
        project.path = str(root)
        session.add(project)
        session.commit()
        log = BuildRunner(session).run_build(project, executor=_succeed_executor)
        assert log.success is True
        assert log.commands.get("build") == "cmake --build build"


def test_build_runner_success(tmp_db):
    with Session(connection.get_engine()) as session:
        project = _project_with_commands(session, {"build": "echo hello"})
        log = BuildRunner(session).run_build(project, executor=_succeed_executor)
        session.refresh(log)
        assert log.success is True
        assert log.exit_code == 0
        assert log.stdout == "built ok\n"
        assert log.commands == {"build": "echo hello"}


def _fail_executor(command, cwd=None):  # noqa: U100
    return _fake_result(exit_code=1, stderr="boom")


def _succeed_executor(command, cwd=None):  # noqa: U100
    return _fake_result(stdout="built ok\n")


def test_build_runner_failure(tmp_db):
    with Session(connection.get_engine()) as session:
        project = _project_with_commands(session, {"build": "make"})
        log = BuildRunner(session).run_build(project, executor=_fail_executor)
        assert log.success is False
        assert log.exit_code == 1
        assert log.stderr == "boom"


def _timeout_executor(command, cwd=None):
    result = _fake_result(exit_code=-1, stderr="slow", stdout="")
    result.timed_out = True
    result.duration_seconds = 300.0
    return result


def test_build_runner_timeout(tmp_db):
    with Session(connection.get_engine()) as session:
        project = _project_with_commands(session, {"build": "sleep 9999"})
        log = BuildRunner(session).run_build(project, executor=_timeout_executor)
        assert log.success is False
        assert "timed out" in log.stderr


# --- v1.17.8.0 build->open -----------------------------------------------


class _FakePopen:
    """Records detached launches instead of spawning real apps."""

    calls: list[dict] = []
    error: Exception | None = None

    def __init__(
        self,
        command,
        shell=False,
        cwd=None,
        stdin=None,
        stdout=None,
        stderr=None,
        creationflags=0,
        env=None,
    ):
        if _FakePopen.error:
            raise _FakePopen.error
        _FakePopen.calls.append({"command": command, "cwd": cwd})


@pytest.fixture()
def fake_popen(monkeypatch):
    import types

    fake = types.SimpleNamespace(DEVNULL=None, STDOUT=None, Popen=_FakePopen)
    monkeypatch.setattr("app.services.build_runner.subprocess", fake)
    _FakePopen.calls = []
    _FakePopen.error = None
    yield _FakePopen


def _project_at(session, commands: dict, root) -> Project:
    project = _project_with_commands(session, commands)
    project.path = str(root)
    session.add(project)
    session.commit()
    return project


def test_build_runner_launch_lands_child_output_in_app_log(tmp_db, tmp_path):
    """v1.17.8.2 regression: the launched app's own output must reach
    data/logs/apps/<slug>.log. Real subprocess — DETACHED_PROCESS made
    cmd.exe spawn external children with invalid stdio (output vanished);
    CREATE_NEW_PROCESS_GROUP alone must capture the whole chain."""
    root = tmp_path / "loggy-app"
    root.mkdir()
    startup = (
        f'echo BUILTIN && "{sys.executable}" -c ' "\"print('CHILD_OUT', flush=True)\""
    )
    with Session(connection.get_engine()) as session:
        project = _project_at(session, {"startup": startup}, root)
        log = BuildRunner(session).run_build(project)
        assert log.launch_command is not None

    log_path = (
        Path(connection.settings.db_path).parent.parent / "logs" / "apps" / "Demo.log"
    )
    content = ""
    for _ in range(50):  # the child writes asynchronously
        content = log_path.read_text(encoding="utf-8")
        # the marker line echoes the command (which contains the literal
        # CHILD_OUT), so a real capture must show the line TWICE.
        if content.count("CHILD_OUT") >= 2 and "BUILTIN" in content:
            break
        time.sleep(0.1)
    assert "BUILTIN" in content, content
    assert content.count("CHILD_OUT") >= 2, content
    assert "[sentinel] App launched" in content, content


def test_build_runner_launches_app_when_no_build(tmp_db, tmp_path, fake_popen):
    root = tmp_path / "run-only-app"
    root.mkdir()
    (root / "app.py").write_text("print('hi')\n", encoding="utf-8")
    with Session(connection.get_engine()) as session:
        project = _project_at(session, {"startup": "python app.py"}, root)
        log = BuildRunner(session).run_build(project)
        assert log.success is True
        assert log.exit_code is None
        assert "no compile step" in (log.stdout or "")
        assert "App launched" in (log.stdout or "")
        assert log.launch_command == "python app.py"
        assert fake_popen.calls[0]["command"] == "python app.py"
        assert fake_popen.calls[0]["cwd"] == str(root)


def test_build_runner_launch_uses_repo_venv_python(tmp_db, tmp_path, fake_popen):
    """The app is launched through the repo's own venv interpreter — a bare
    `python` on the global PATH may not have the app's deps (AG: .venv_sf3d)."""
    root = tmp_path / "venv-app"
    root.mkdir()
    venv = root / ".venv_sf3d" / "Scripts"
    venv.mkdir(parents=True)
    (venv / "python.exe").write_text("dummy")
    with Session(connection.get_engine()) as session:
        project = _project_at(
            session, {"startup": "python -m streamlit run dashboard/app.py"}, root
        )
        log = BuildRunner(session).run_build(project)
        assert log.launch_command is not None
        assert ".venv_sf3d" in log.launch_command
        assert log.launch_command.startswith('"')
        assert "-m streamlit run dashboard/app.py" in log.launch_command

    marker_path = (
        Path(connection.settings.db_path).parent.parent / "logs" / "apps" / "Demo.log"
    )
    assert "[sentinel] App launched" in marker_path.read_text(encoding="utf-8")


def test_build_runner_launch_rewrites_venv_console_scripts(
    tmp_db, tmp_path, fake_popen
):
    """v1.17.8.0: venv console-script binaries (uvicorn, like pytest) are
    rewritten to the venv interpreter's `-m` form — demake's
    `cd backend && uvicorn main:app --reload` must not depend on the global
    PATH."""
    root = tmp_path / "venv-uvicorn"
    root.mkdir()
    (root / "backend").mkdir()
    venv = root / "venv" / "Scripts"
    venv.mkdir(parents=True)
    (venv / "python.exe").write_text("dummy")
    with Session(connection.get_engine()) as session:
        project = _project_at(
            session, {"startup": "cd backend && uvicorn main:app --reload"}, root
        )
        log = BuildRunner(session).run_build(project)
        assert log.launch_command is not None
        assert log.launch_command.startswith('cd backend && "')
        assert 'python.exe" -m uvicorn main:app --reload' in log.launch_command
        assert "venv" in log.launch_command


def test_build_runner_does_not_double_rewrite_venv_uvicorn(
    tmp_db, tmp_path, fake_popen
):
    """v1.17.11.0 regression: a tester launch that already embeds the venv
    interpreter with `-m uvicorn` must stay a single rewrite — the old regex
    produced `"<venv>\\python.exe" -m "<venv>\\python.exe" -m uvicorn …`
    (ModuleNotFoundError, port never bound)."""
    root = tmp_path / "venv-uvicorn-already"
    root.mkdir()
    venv = root / "venv" / "Scripts"
    venv.mkdir(parents=True)
    (venv / "python.exe").write_text("dummy")
    embedded = f'"{root}\\venv\\Scripts\\python.exe" -m uvicorn backend.main:app'
    with Session(connection.get_engine()) as session:
        project = _project_at(session, {"startup": embedded}, root)
        log = BuildRunner(session).run_build(project)
        assert log.launch_command is not None
        assert log.launch_command == embedded
        assert 'python.exe" -m "' not in log.launch_command


def test_build_runner_does_not_launch_on_failure(tmp_db, tmp_path, fake_popen):
    """A failed build never opens the app."""
    root = tmp_path / "broken-app"
    root.mkdir()
    with Session(connection.get_engine()) as session:
        project = _project_at(
            session, {"build": "make", "startup": "python app.py"}, root
        )
        log = BuildRunner(session).run_build(project, executor=_fail_executor)
        assert log.success is False
        assert log.launch_command is None
        assert fake_popen.calls == []


def test_build_runner_launches_app_after_success(tmp_db, tmp_path, fake_popen):
    """build -> open: a green build launches the app."""
    root = tmp_path / "builds-app"
    root.mkdir()
    with Session(connection.get_engine()) as session:
        project = _project_at(
            session, {"build": "npm run build", "startup": "npm run start"}, root
        )
        log = BuildRunner(session).run_build(project, executor=_succeed_executor)
        assert log.success is True
        assert log.launch_command == "npm run start"
        assert "App launched" in (log.stdout or "")


def test_build_runner_launch_failure_recorded(tmp_db, tmp_path, fake_popen):
    """A launch that cannot spawn is recorded honestly, not as a pass."""
    root = tmp_path / "unlaunchable"
    root.mkdir()
    fake_popen.error = OSError("no such binary")
    with Session(connection.get_engine()) as session:
        project = _project_at(session, {"startup": "python app.py"}, root)
        log = BuildRunner(session).run_build(project)
        assert log.success is True
        assert log.launch_command is None
        assert "App launch failed" in (log.stdout or "")


class _FakeSubprocess:
    """Replaces subprocess inside build_runner: records Popen/run calls and
    feeds a fixed netstat body — nothing real is ever spawned."""

    DEVNULL = None
    STDOUT = None
    calls = []
    netstat_out = ""
    startfile_calls = []

    @classmethod
    def Popen(cls, *args, **kwargs):  # noqa: U100
        cls.calls.append(("popen", args[0], kwargs.get("cwd")))
        return object()

    @classmethod
    def run(cls, args, **kwargs):  # noqa: U100
        cls.calls.append(("run", args))
        return types.SimpleNamespace(stdout=cls.netstat_out)


@pytest.fixture()
def fake_subprocess(monkeypatch):
    monkeypatch.setattr("app.services.build_runner.subprocess", _FakeSubprocess)
    _FakeSubprocess.calls = []
    _FakeSubprocess.netstat_out = ""
    _FakeSubprocess.startfile_calls = []
    monkeypatch.setattr(
        "app.services.build_runner.os.startfile",
        _FakeSubprocess.startfile_calls.append,
    )
    yield _FakeSubprocess


def _project_named(session, name: str, startup: str, root) -> Project:
    project = Project(
        id=f"p-{name.lower()}",
        name=name,
        path=str(root),
        language="javascript",
        stack={"commands": {"startup": startup}},
    )
    session.add(project)
    session.commit()
    return project


def test_build_runner_open_frees_ports_launches_extras_and_opens_browser(
    tmp_db, tmp_path, fake_subprocess
):
    """v1.17.13.4: build->open for a browser-served app (Card-Game) kills
    listeners on its declared ports, launches the stored startup plus the
    extra backend server, and opens the default browser at the web_url."""
    fake_subprocess.netstat_out = (
        "TCP    0.0.0.0:5173    0.0.0.0:0    LISTENING    11111\n"
        "TCP    [::1]:3000      [::]:0       LISTENING    22222\n"
        "TCP    0.0.0.0:5174    0.0.0.0:0    LISTENING    33333\n"
        "UDP    0.0.0.0:3000    0.0.0.0:0                44444\n"
    )
    root = tmp_path / "card-game-open"
    root.mkdir()
    with Session(connection.get_engine()) as session:
        project = _project_named(
            session, "Card-Game", "cd frontend && npm run dev", root
        )
        log = BuildRunner(session).run_build(project)
        session.refresh(log)
        assert log.success is True
        assert log.launch_command == "cd frontend && npm run dev"
        assert "Freed ports for restart: 11111, 22222" in (log.stdout or "")
        assert "App opened: http://localhost:5173" in (log.stdout or "")
    commands = [c[1] for c in _FakeSubprocess.calls if c[0] == "run"]
    assert ["netstat", "-ano"] in commands
    assert ["taskkill", "/F", "/PID", "11111"] in commands
    assert ["taskkill", "/F", "/PID", "22222"] in commands
    # a drift port (5174) is not the app's — never killed
    assert all(c != ["taskkill", "/F", "/PID", "33333"] for c in commands)
    popens = [c[1] for c in _FakeSubprocess.calls if c[0] == "popen"]
    assert popens == ["cd frontend && npm run dev", "cd backend && node server.js"]
    assert _FakeSubprocess.startfile_calls == ["http://localhost:5173"]


def test_build_runner_open_no_listeners_still_launches_and_opens(
    tmp_db, tmp_path, fake_subprocess
):
    """No listener on the app's ports -> nothing to kill; the launch and the
    browser open still happen."""
    root = tmp_path / "card-game-cold"
    root.mkdir()
    with Session(connection.get_engine()) as session:
        project = _project_named(
            session, "Card-Game", "cd frontend && npm run dev", root
        )
        log = BuildRunner(session).run_build(project)
        assert log.success is True
        assert "none listening" in (log.stdout or "")
        assert "App opened: http://localhost:5173" in (log.stdout or "")
    runs = [c[1] for c in _FakeSubprocess.calls if c[0] == "run"]
    assert all(c[0] != "taskkill" for c in runs)


def test_build_runner_open_desktop_app_opens_no_browser(
    tmp_db, tmp_path, fake_subprocess
):
    """v1.17.13.4: a desktop app (Cg — Electron, no web_url) is launched
    with no browser. v1.17.18.5 (audit2 T11): Cg now declares ports=(8000,)
    like Demake/WFT, so its own dev-server port is freed before relaunch."""
    root = tmp_path / "cg-open"
    root.mkdir()
    with Session(connection.get_engine()) as session:
        project = _project_named(
            session, "Cg", "cd renderer && npm run electron-dev", root
        )
        log = BuildRunner(session).run_build(project)
        assert log.success is True
        assert log.launch_command == "cd renderer && npm run electron-dev"
        assert "App opened" not in (log.stdout or "")
        assert "Freed ports" in (log.stdout or "")
    assert _FakeSubprocess.startfile_calls == []
    popens = [c[1] for c in _FakeSubprocess.calls if c[0] == "popen"]
    assert popens == ["cd renderer && npm run electron-dev"]


# --- TestRunner unit tests ---


def test_parse_test_output_pytest_summary():
    parsed = RunnerService.parse_test_output(
        "tests/test_app.py::test_item PASSED ...\n"
        "5 passed, 2 failed, 3 skipped in 0.42s",
        "",
    )
    assert parsed == {"passed": 5, "failed": 2, "errors": 0, "skipped": 3}


def test_parse_test_output_errors():
    parsed = RunnerService.parse_test_output("", "1 error in 0.01s")
    assert parsed["errors"] == 1
    assert parsed["passed"] == 0


def _test_executor(command, cwd=None):
    return _fake_result(stdout="2 passed, 0 failed\n")


def test_test_runner_creates_result(tmp_db):
    project_id = _seed(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RunnerService.get_project(session, project_id)
        result = RunnerService(session).run_tests(project, executor=_test_executor)
        assert result.framework == "pytest"
        assert result.passed == 2
        assert result.summary == "2 passed, 0 failed"
        assert result.duration_seconds is not None


def test_test_runner_framework_detects_venv_qualified_pytest(tmp_db):
    """v1.17.7.7: a venv-qualified command
    (`"C:\\repo\\.venv\\Scripts\\python.exe" -m pytest`) still reports
    framework pytest."""
    project_id = _seed(tmp_db)
    with Session(connection.get_engine()) as session:
        project = RunnerService.get_project(session, project_id)
        result = RunnerService(session).run_tests(
            project,
            executor=lambda command, cwd=None: _fake_result(
                stdout="2 passed, 0 failed\n"
            ),
        )
        assert result.framework == "pytest"
        assert result.passed == 2


# --- SecurityScanner unit tests ---


def test_security_scanner_finds_all_types(tmp_db):
    project_id = _seed(tmp_db, SCAN_FIXTURE)
    with Session(connection.get_engine()) as session:
        project = SecurityScanner.get_project(session, project_id)
        findings = SecurityScanner(session).scan_project(project)
        types = {f.type for f in findings}
        assert {"vulnerability", "secret", "static_analysis"} <= types
        severities = {f.severity.value for f in findings}
        assert {"high", "medium"} <= severities
        by_type = {f.type: f for f in findings}
        assert by_type["secret"].file_path.replace("\\", "/") == "app/config.py"
        assert "AKIA" in by_type["secret"].title or (
            by_type["secret"].title == "AWS Access Key detected"
        )
        assert by_type["vulnerability"].title.startswith("Known vulnerable")
        assert by_type["static_analysis"].file_path.endswith("func.py")


def test_security_scanner_clean_project(tmp_db):
    project_id = _seed(tmp_db)
    with Session(connection.get_engine()) as session:
        project = SecurityScanner.get_project(session, project_id)
        findings = SecurityScanner(session).scan_project(project)
        assert findings == []


def test_security_scanner_stamps_last_scanned_even_when_clean(tmp_db):
    """v1.17.6.6: EVERY scan — clean included — stamps `project.last_scanned`,
    so the portfolio can show ✓ "clean" instead of ✗ "pending" forever (a
    clean scan previously stored no rows at all)."""
    project_id = _seed(tmp_db)
    with Session(connection.get_engine()) as session:
        project = SecurityScanner.get_project(session, project_id)
        assert project.last_scanned is None
        SecurityScanner(session).scan_project(project)
        session.refresh(project)
        assert project.last_scanned is not None


def test_security_scanner_skips_false_positives(tmp_db, tmp_path):
    """Sprint 15: data/, fixtures/, .env templates and test files are not
    application source — scanning them must not produce findings."""
    root = tmp_path / "app-project"
    (root / "data" / "pihole" / "etc-pihole").mkdir(parents=True)
    (root / "data" / "pihole" / "etc-pihole" / "tls.pem").write_text(
        "-----BEGIN PRIVATE KEY-----", encoding="utf-8"
    )
    (root / "fixtures").mkdir()
    (root / "fixtures" / "sample.py").write_text(
        'AWS_ACCESS_KEY = "AKIA1234567890ABCDEF"', encoding="utf-8"
    )
    (root / ".env.example").write_text(
        "SENTINEL_GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx", encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_stuff.py").write_text(
        "def test_compiles():\n    exec('x = 1')\n", encoding="utf-8"
    )
    (root / "app").mkdir()
    (root / "app" / "real.py").write_text(
        "TOKEN = 'ghp_abcdefghijklmnopqrst'\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n", encoding="utf-8"
    )

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        findings = SecurityScanner(session).scan_project(project)
        # Only the real code secret is flagged — no data/, fixtures/,
        # .env.example, and no exec() inside test files.
        assert len(findings) == 1
        assert findings[0].type == "secret"
        assert findings[0].file_path.replace("\\", "/") == "app/real.py"


def test_static_analysis_ignores_attribute_calls(tmp_db, tmp_path):
    """v1.17.1 regression: '\\bexec\\s*\\(' matched `session.exec(` because a
    dot is a word boundary — every SQLModel project was flagged for its ORM
    calls (17 of the laptop's 20 findings were this false positive). AST-based
    detection only flags bare Name calls, so attribute calls still pass."""
    root = tmp_path / "orm-project"
    root.mkdir()
    (root / "service.py").write_text(
        "from sqlmodel import Session, select\n\n"
        "def query(session: Session):\n"
        "    return session.exec(select(Model)).all()\n"
        "    obj.eval(1, 2)\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        assert SecurityScanner(session).scan_project(project) == []


def test_static_analysis_ignores_string_literals(tmp_db, tmp_path):
    """v1.17.7.5 regression: the regex static scan flagged the string
    literals `"Use of eval()"`/`"Use of exec()"` in the scanner's own
    pattern titles — Sentinel flagged itself 3×. AST detection only flags
    real calls, so strings and comments can never match."""
    root = tmp_path / "string-project"
    root.mkdir()
    (root / "app.py").write_text(
        'MSG = "Use of eval() and Use of exec() in this string"\n'
        "# ghp_xxxxxxxxxxxxxxxxxxxx\n"
        "TITLE = 'Use of eval()'\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        assert SecurityScanner(session).scan_project(project) == []


def test_scanner_scans_indexed_files_only(tmp_db, tmp_path):
    """v1.17.7.5: the scan covers the project's *indexed* files (git-tracked,
    indexer gates applied) — never the raw tree. Untracked junk
    (.venv_sf3d site-packages, electron release output) exists on disk but
    must not produce findings; the real tracked source still is."""
    root = tmp_path / "indexed-project"
    (root / "app").mkdir(parents=True)
    (root / "app" / "real.py").write_text(
        "result = exec(user_input())\n", encoding="utf-8"
    )
    junk_venv = root / ".venv_sf3d" / "Lib" / "site-packages"
    junk_venv.mkdir(parents=True)
    (junk_venv / "vendored.py").write_text("x = eval('1+1')\n", encoding="utf-8")
    release = root / "release" / "bundle.js"
    release.parent.mkdir()
    release.write_text("const key = 'AKIA1234567890ABCDEF';\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        indexed = {
            f.path.replace("\\", "/")
            for f in session.exec(
                select(ProjectFile).where(ProjectFile.project_id == project.id)
            ).all()
        }
        assert not any(
            p.startswith(".venv_sf3d") or p.startswith("release") for p in indexed
        )
        findings = SecurityScanner(session).scan_project(project)
        paths = {f.file_path.replace("\\", "/") for f in findings}
        assert paths == {"app/real.py"}
        assert {f.title for f in findings} == {"Use of exec()"}


def test_static_analysis_still_flags_bare_exec(tmp_db, tmp_path):
    root = tmp_path / "exec-project"
    root.mkdir()
    (root / "danger.py").write_text(
        "command = user_input()\nresult = exec(command)\nvalue = eval('1+1')\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        findings = SecurityScanner(session).scan_project(project)
        titles = {f.title for f in findings}
    assert {"Use of exec()", "Use of eval()"} <= titles


def test_placeholder_secrets_are_not_flagged(tmp_db, tmp_path):
    """v1.17.1: example/placeholder values (all-same-char tokens, `xxx`,
    `example`, test fixtures) are not real secrets."""
    root = tmp_path / "template-project"
    root.mkdir()
    (root / "config.py").write_text(
        "OPENAI = 'sk-xxx'\n"
        "TOKEN = 'ghp_xxxxxxxxxxxxxxxxxxxx'\n"
        "API = 'AIzaSyEXAMPLEaaaaaaaaaaa'\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        findings = SecurityScanner(session).scan_project(project)
        secret_flags = [f for f in findings if f.type == "secret"]
    assert secret_flags == []


def test_secret_scanning_skips_test_files(tmp_db, tmp_path):
    """v1.17.1: fake credentials in test files (the laptop's
    'test_automation.py has keys' finding) must not be flagged — consistent
    with static analysis."""
    root = tmp_path / "test-secrets-project"
    root.mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "test_auth.py").write_text(
        "TOKEN = 'ghp_abcdefghijklmnopqrst'\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        findings = SecurityScanner(session).scan_project(project)
        secret_flags = [f for f in findings if f.type == "secret"]
    assert secret_flags == []


def test_openssl_stack_api_not_flagged_as_secret(tmp_db, tmp_path):
    """v1.17.7.5 live catch: OpenSSL's `sk_X509_INFO_pop_free` stack-API
    matched the generic `sk` secret prefix (Algo Trader, httplib.h:14708).
    Stripe keys require the full sk_live_/sk_test_ forms now."""
    root = tmp_path / "cpp-project"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src" / "tls.cc").write_text(
        "sk_X509_INFO_pop_free(inf, X509_INFO_free);\n"
        "auto obj = sk_X509_OBJECT_value(objs, i);\n",
        encoding="utf-8",
    )
    (root / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n")

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        findings = SecurityScanner(session).scan_project(project)
        secret_flags = [f for f in findings if f.type == "secret"]
    assert secret_flags == []


def test_stripe_keys_still_flagged(tmp_db, tmp_path):
    """sk_live_/sk_test_ payloads must still trip the generic secret rule.
    (The payload is assembled at runtime so no literal key ever lands in
    source — GitHub push protection flags the plaintext form.)"""
    root = tmp_path / "stripe-project"
    root.mkdir()
    payload = "abcdefghijklmnopqrstuvwxyz012345"
    (root / "pay.py").write_text("KEY = 'sk_live_" + payload + "'\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        findings = SecurityScanner(session).scan_project(project)
        secret_flags = [f for f in findings if f.type == "secret"]
    assert len(secret_flags) == 1


# --- API integration (eager Celery) ---


def test_build_run_status_and_history(eager, tmp_db):
    """v1.17.7.5: a project with no build command completes as "skipped"
    (success=None) — it must not claim a pass it never ran."""
    project_id = _seed(tmp_db)
    resp = client.post("/api/v1/builds/run", json={"project_id": project_id})
    assert resp.status_code == 202
    body = resp.json()
    assert body["project_id"] == project_id
    assert body["status"] == "skipped"
    assert body["exit_code"] is None

    status = client.get(f"/api/v1/builds/status/{body['id']}")
    assert status.status_code == 200
    assert status.json()["status"] == "skipped"

    history = client.get("/api/v1/builds/history", params={"project_id": project_id})
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_build_run_unknown_project_404(eager, tmp_db):
    resp = client.post("/api/v1/builds/run", json={"project_id": "nope"})
    assert resp.status_code == 404


def test_build_status_unknown_404(eager, tmp_db):
    resp = client.get("/api/v1/builds/status/does-not-exist")
    assert resp.status_code == 404


def test_tests_run_and_results(eager, tmp_db):
    project_id = _seed(tmp_db)
    resp = client.post("/api/v1/tests/run", params={"project_id": project_id})
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"

    results = client.get("/api/v1/tests/results", params={"project_id": project_id})
    assert results.status_code == 200
    rows = results.json()
    assert len(rows) == 1
    assert rows[0]["framework"] == "pytest"
    assert rows[0]["summary"] is not None


def test_security_scan_is_idempotent(tmp_db):
    """Sprint 16: re-scanning a project must not re-insert duplicate rows —
    only *new* findings are returned, existing ones are reused."""
    from app.db.models import SecurityFinding

    project_id = _seed(tmp_db, SCAN_FIXTURE)
    with Session(connection.get_engine()) as session:
        project = SecurityScanner.get_project(session, project_id)
        first = SecurityScanner(session).scan_project(project)
        assert len(first) > 0
        second = SecurityScanner(session).scan_project(project)
        assert second == []
        open_rows = session.exec(
            select(SecurityFinding).where(
                SecurityFinding.project_id == project_id,
                SecurityFinding.resolved == False,  # noqa: E712
            )
        ).all()
        assert len(open_rows) == len(first)


def test_security_scan_resolves_stale_findings(tmp_db, tmp_path):
    """Sprint 16: when a file no longer matches any pattern, its open finding
    is marked resolved instead of piling up."""
    from app.db.models import SecurityFinding

    root = tmp_path / "app"
    root.mkdir()
    (root / "leak.py").write_text("TOKEN = 'ghp_abcdefghijklmnopqrst'\n")
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        scanner = SecurityScanner(session)
        assert len(scanner.scan_project(project)) == 1
        (root / "leak.py").write_text("TOKEN = 'safe'\n")
        assert scanner.scan_project(project) == []
        rows = session.exec(
            select(SecurityFinding).where(SecurityFinding.project_id == project.id)
        ).all()
        assert len(rows) == 1
        assert rows[0].resolved is True


def test_security_scan_and_findings(eager, tmp_db):
    project_id = _seed(tmp_db, SCAN_FIXTURE)
    resp = client.post("/api/v1/security/scan", params={"project_id": project_id})
    assert resp.status_code == 202

    findings = client.get(
        "/api/v1/security/findings", params={"project_id": project_id}
    )
    assert findings.status_code == 200
    types = {f["type"] for f in findings.json()}
    assert {"vulnerability", "secret", "static_analysis"} <= types


def test_security_scan_all(eager, tmp_db):
    first = _seed(tmp_db, SCAN_FIXTURE)
    second = _seed(tmp_db, PYTHON_FIXTURE)
    resp = client.post("/api/v1/security/scan-all")
    assert resp.status_code == 202

    with Session(connection.get_engine()) as session:
        for project_id in (first, second):
            project = session.get(Project, project_id)
            assert project.last_scanned is not None
        dirty = session.exec(
            select(SecurityFinding).where(SecurityFinding.project_id == first)
        ).all()
        assert dirty, "scan-all should scan every project"
        assert len(dirty) > 0


def test_security_clear_resolved_findings(eager, tmp_db):
    """v1.17.7.7: DELETE /security/findings removes only *resolved* rows —
    open findings survive (they are the current scan state)."""
    project_id = _seed(tmp_db, SCAN_FIXTURE)
    scan = client.post("/api/v1/security/scan", params={"project_id": project_id})
    assert scan.status_code == 202

    before = client.get("/api/v1/security/findings", params={"project_id": project_id})
    assert before.status_code == 200
    total = len(before.json())
    assert total > 0

    with Session(connection.get_engine()) as session:
        row = session.exec(
            select(SecurityFinding).where(SecurityFinding.project_id == project_id)
        ).first()
        row.resolved = True
        session.add(row)
        session.commit()

    resp = client.delete("/api/v1/security/findings", params={"project_id": project_id})
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 1}

    after = client.get("/api/v1/security/findings", params={"project_id": project_id})
    assert after.status_code == 200
    rows = after.json()
    assert len(rows) == total - 1
    assert all(not row["resolved"] for row in rows)


def test_security_clear_resolved_unknown_project(eager, tmp_db):
    resp = client.delete("/api/v1/security/findings", params={"project_id": "missing"})
    assert resp.status_code == 404


def test_security_clear_resolved_is_resolved_only(eager, tmp_db):
    """A second delete after resolution is a no-op — and open findings are
    never deletable via this endpoint."""
    project_id = _seed(tmp_db, SCAN_FIXTURE)
    scan = client.post("/api/v1/security/scan", params={"project_id": project_id})
    assert scan.status_code == 202
    client.delete("/api/v1/security/findings", params={"project_id": project_id})
    again = client.delete(
        "/api/v1/security/findings", params={"project_id": project_id}
    )
    assert again.json() == {"deleted": 0}
    with Session(connection.get_engine()) as session:
        open_rows = session.exec(
            select(SecurityFinding).where(
                SecurityFinding.project_id == project_id,
                SecurityFinding.resolved == False,  # noqa: E712
            )
        ).all()
        assert open_rows, "open findings are the live scan state and survive"
