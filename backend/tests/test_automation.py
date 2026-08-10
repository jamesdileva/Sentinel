"""Sprint 7: build/test/security runner unit tests + API integration."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import connection
from app.db.models import Project
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
    with Session(connection.get_engine()) as session:
        project = _project_with_commands(session, {})
        log = BuildRunner(session).run_build(project)
        assert log.success is True
        assert log.exit_code == 0
        assert log.completed_at is not None
        assert log.commands.get("build") == ""


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
    calls (17 of the laptop's 20 findings were this false positive)."""
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

    from app.services.security_scanner import _STATIC_PATTERNS

    content = (root / "service.py").read_text(encoding="utf-8")
    for _name, pattern, _severity in _STATIC_PATTERNS:
        assert pattern.findall(content) == []

    with Session(connection.get_engine()) as session:
        project = IndexerService(session).index_project(str(root))
        assert SecurityScanner(session).scan_project(project) == []


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


# --- API integration (eager Celery) ---


def test_build_run_status_and_history(eager, tmp_db):
    project_id = _seed(tmp_db)
    resp = client.post("/api/v1/builds/run", json={"project_id": project_id})
    assert resp.status_code == 202
    body = resp.json()
    assert body["project_id"] == project_id
    assert body["status"] == "succeeded"
    assert body["exit_code"] == 0

    status = client.get(f"/api/v1/builds/status/{body['id']}")
    assert status.status_code == 200
    assert status.json()["status"] == "succeeded"

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
