"""Sprint 7: build/test/security runner unit tests + API integration."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import connection
from app.db.models import Project
from app.main import app
from app.services.build_runner import BuildRunner
from app.services.command_runner import CommandResult
from app.services.indexer import IndexerService
from app.services.security_scanner import SecurityScanner
from app.services.test_runner import TestRunner as RunnerService
from app.tasks.celery_app import celery_app

client = TestClient(app)

PYTHON_FIXTURE = "tests/fixtures/sample_python_project"
SCAN_FIXTURE = "tests/fixtures/sample_scan_project"


@pytest.fixture()
def eager(monkeypatch):
    """Run Celery tasks synchronously so tests need no broker."""
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)


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
