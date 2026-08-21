"""Sprint 11: hardening tests for repositories, parsers, runners, git_history.

Fills the remaining coverage gaps in deterministic modules: the generic
Repository CRUD + concrete filtering queries, file-path parser dispatch, sql/
node parser branches, FastAPI/Flask route extraction, subprocess error paths
(timeout/OSError), and git log parsing edge cases.
"""

from types import SimpleNamespace

import pytest
from sqlmodel import Session

from app.core.config import settings
from app.db.connection import get_engine
from app.db.models import (
    Dependency,
    GitCommit,
    Project,
    SecurityFinding,
    Severity,
)
from app.parsers import (
    FastAPIParser,
    NodeParser,
    SQLParser,
    parse_file_for_project,
    parser_for_language,
)
from app.repositories import (
    DependencyRepository,
    ProjectRepository,
    SecurityRepository,
)
from app.repositories.base import Repository
from app.services import git_history
from app.services.command_runner import run_command

parse_log = git_history.parse_log


def _session():
    return Session(get_engine(), expire_on_commit=False)


# --- Repository base -----------------------------------------------------------


def test_repository_base_crud(tmp_db):
    with _session() as session:
        repo = ProjectRepository(session)
        project = Project(name="crud", path="/crud", language="python")
        repo.add(project)
        project.health_score = 42
        repo.update(project)
        assert repo.get(project.id) is not None
        assert len(repo.list()) >= 1
        assert repo.count() >= 1
        repo.delete(project)
        assert repo.get(project.id) is None


def test_repository_requires_model():
    class Bare(Repository):
        pass

    with pytest.raises(TypeError):
        with _session() as session:
            Bare(session)


def test_repository_constructor_model_override(tmp_db):
    with _session() as session:
        repo = Repository(session, model=Project)
        assert repo.list() == []


def test_repository_list_skip_limit(tmp_db):
    with _session() as session:
        repo = Repository(session, model=Project)
        for index in range(3):
            repo.add(Project(name=f"s{index}", path=f"/p{index}", language="python"))
        page = repo.list(skip=1, limit=1)
        assert [p.name for p in page] == ["s1"]


# --- ProjectRepository ---------------------------------------------------------


def test_project_repository_queries(tmp_db):
    with _session() as session:
        repo = ProjectRepository(session)
        one = repo.add(Project(name="p-one", path="/a", language="python"))
        repo.add(Project(name="p-two", path="/b", language="python", status="inactive"))
        assert repo.get_by_path("/a").id == one.id
        assert repo.get_by_path("/nope") is None


# --- SecurityRepository --------------------------------------------------------


def test_security_repository_filters(tmp_db):
    with _session() as session:
        project = Project(name="sec", path="/s", language="python")
        session.add(project)
        session.flush()
        session.add_all(
            [
                SecurityFinding(
                    project_id=project.id,
                    type="secret",
                    severity=Severity.HIGH,
                    title="open",
                ),
                SecurityFinding(
                    project_id=project.id,
                    type="secret",
                    severity=Severity.LOW,
                    title="resolved",
                    resolved=True,
                ),
            ]
        )
        session.commit()
        repo = SecurityRepository(session)
        assert [f.title for f in repo.get_by_project(project.id)] == [
            "resolved",
            "open",
        ]
        assert [f.title for f in repo.get_open(project.id)] == ["open"]


def test_security_repository_delete_resolved(tmp_db):
    """v1.17.7.7: delete_resolved removes only resolved rows and reports the
    count."""
    with _session() as session:
        project = Project(name="sec2", path="/s2", language="python")
        session.add(project)
        session.flush()
        session.add_all(
            [
                SecurityFinding(
                    project_id=project.id,
                    type="secret",
                    severity=Severity.HIGH,
                    title="open",
                ),
                SecurityFinding(
                    project_id=project.id,
                    type="secret",
                    severity=Severity.LOW,
                    title="resolved-a",
                    resolved=True,
                ),
                SecurityFinding(
                    project_id=project.id,
                    type="secret",
                    severity=Severity.LOW,
                    title="resolved-b",
                    resolved=True,
                ),
            ]
        )
        session.commit()
        repo = SecurityRepository(session)
        assert repo.delete_resolved(project.id) == 2
        assert [f.title for f in repo.get_by_project(project.id)] == ["open"]


# --- DependencyRepository ------------------------------------------------------


def test_dependency_repository(tmp_db):
    with _session() as session:
        project = Project(name="d", path="/d", language="python")
        session.add(project)
        session.flush()
        session.add_all(
            [
                Dependency(project_id=project.id, name="pkg-a", version="1"),
                Dependency(project_id=project.id, name="pkg-b", version="2"),
            ]
        )
        session.commit()
        repo = DependencyRepository(session)
        assert {d.name for d in repo.get_by_project(project.id)} == {"pkg-a", "pkg-b"}
        # v1.17.18.4 (audit2 D5): the optional limit is honored.
        assert len(repo.get_by_project(project.id, limit=1)) == 1
        repo.delete_by_project(project.id)
        assert repo.get_by_project(project.id) == []


# --- parsers --------------------------------------------------------------------


def test_parser_for_language():
    assert parser_for_language("python") is not None
    assert parser_for_language("nope") is None


def test_node_parser_invalid_and_valid():
    parser = NodeParser()
    assert parser.extract_structure("{broken") == {"error": "invalid_json"}
    assert parser._extract_dependencies("{broken") == []
    valid = parser.extract_structure('{"name":"n","scripts":{"build":"t"}}')
    assert valid["name"] == "n"
    assert valid["scripts"] == {"build": "t"}


def test_node_parser_file(tmp_path):
    file = tmp_path / "package.json"
    file.write_text('{"name":"x","dependencies":{"lodash":"1"}}')
    parsed = NodeParser().parse_file(str(file))
    assert parsed.language == "json"
    assert "lodash" in parsed.dependencies


def test_sql_parser():
    content = (
        "CREATE TABLE users (\n"
        "  id INTEGER PRIMARY KEY,\n"
        "  email VARCHAR(255)\n"
        ");\n"
        "SELECT * FROM users;"
    )
    structure = SQLParser().extract_structure(content)
    assert structure["tables"][0]["name"] == "users"
    assert structure["tables"][0]["columns"][1]["name"] == "email"
    assert structure["tables"][0]["columns"][1]["type"] == "VARCHAR"
    assert "SELECT" in structure["statements"]


def test_sql_parser_file(tmp_path):
    file = tmp_path / "schema.sql"
    file.write_text("CREATE TABLE t (id INT);")
    assert SQLParser().parse_file(str(file)).structure["tables"][0]["name"] == "t"


def test_file_dispatch(tmp_path):
    tsx = tmp_path / "card.tsx"
    tsx.write_text("const x = 1;")
    ts = tmp_path / "util.ts"
    ts.write_text("const y = 2;")
    js = tmp_path / "lib.js"
    js.write_text("var z = 3;")
    pkg = tmp_path / "package.json"
    pkg.write_text('{"name":"p"}')
    sql = tmp_path / "schema.sql"
    sql.write_text("CREATE TABLE t (id INT);")
    unknown = tmp_path / "blob.unknownext"
    unknown.write_text("x")

    ts_parsed = parse_file_for_project(str(ts), "typescript", None)
    js_parsed = parse_file_for_project(str(js), "javascript", None)
    react_ts = parse_file_for_project(str(ts), "javascript", "react")
    react_js = parse_file_for_project(str(js), "javascript", "react")
    assert parse_file_for_project(str(tsx), "jsx", None) is not None
    assert "interfaces" in ts_parsed.structure  # TypeScriptParser branch
    assert "interfaces" not in js_parsed.structure  # JavaScriptParser branch
    assert "components" in react_ts.structure and "components" in react_js.structure
    pkg_parsed = parse_file_for_project(str(pkg), "json", None)
    assert "scripts" in pkg_parsed.structure  # NodeParser branch (package.json)
    assert parse_file_for_project(str(sql), "sql", None) is not None
    assert parse_file_for_project(str(unknown), "nope", None) is None


def test_file_dispatch_python_framework(tmp_path):
    file = tmp_path / "main.py"
    file.write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get('/')\ndef root():\n    return {}"
    )
    flask_file = tmp_path / "web.py"
    flask_file.write_text("from flask import Flask\napp = Flask(__name__)")

    fastapi_root = parse_file_for_project(str(file), "python", "fastapi")
    flask_root = parse_file_for_project(str(flask_file), "python", "flask")
    plain = parse_file_for_project(str(file), "python", None)
    assert "routes" in fastapi_root.structure
    assert "routes" in flask_root.structure
    assert "routes" not in plain.structure


def test_fastapi_routes_syntax_error():
    parsed = FastAPIParser().extract_structure("def f(:")
    assert parsed["routes"] == []


def test_fastapi_routes_no_decorator_args():
    parsed = FastAPIParser().extract_structure(
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get\ndef f():\n    return {}"
    )
    assert parsed["routes"] == []


def test_fastapi_flask_routes_extracted():
    content = (
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.post('/items')\ndef create():\n    return {}\n"
        "@app.route('/ws')\ndef ws():\n    return {}"
    )
    routes = FastAPIParser().extract_structure(content)["routes"]
    assert routes[0]["method"] == "POST"
    assert routes[1]["method"] == "ROUTE"


# --- command_runner --------------------------------------------------------------


def test_run_command_success():
    result = run_command("echo s11hello")
    assert result.exit_code == 0
    assert "s11hello" in result.stdout
    assert result.timed_out is False


def test_run_command_timeout():
    result = run_command(
        'python -c "import time; time.sleep(5)"',
        timeout=0,
    )
    assert result.timed_out is True
    assert result.exit_code == -1


def test_run_command_oserror(tmp_path):
    result = run_command("echo x", cwd=tmp_path / "definitely-missing-dir")
    assert result.exit_code == -1
    assert result.stderr != ""


def test_run_command_env_overlays_inherited_environment():
    """v1.17.3 regression: passing env= must not wipe PATH (that made every
    `git` invocation fail under the Task Scheduler autostart task)."""
    result = run_command(
        "python -c \"import os; print(os.environ.get('MY_OVERRIDE', '')); "
        "print(os.environ.get('PATH') is not None)\"",
        env={"MY_OVERRIDE": "yes"},
    )
    assert result.exit_code == 0
    assert result.stdout.splitlines() == ["yes", "True"]


def test_resolve_git_uses_configured_executable(monkeypatch, tmp_path):
    from app.services.command_runner import resolve_git

    exe = tmp_path / "git.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "git_executable", str(exe))
    assert resolve_git() == str(exe)


def test_resolve_git_returns_none_when_nothing_found(monkeypatch):
    from app.services import command_runner
    from app.services.command_runner import resolve_git

    monkeypatch.setattr(settings, "git_executable", "")
    monkeypatch.setattr(command_runner.shutil, "which", lambda name: None)
    monkeypatch.setattr(command_runner, "_GIT_CANDIDATES", ())
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert resolve_git() is None


# --- git_history ------------------------------------------------------------------


def test_parse_log_skips_malformed():
    assert parse_log("not-enough-pipes") == []


def test_parse_log_bad_iso():
    items = parse_log("a" * 40 + "|me|bad-date|msg")
    assert items[0]["timestamp"] is None
    assert items[0]["author"] == "me"


def test_parse_log_skip_empty_fields():
    assert parse_log("") == []
    assert parse_log("a" * 40 + "||2024-01-01T00:00:00Z|") == []


def test_analyze_history_skips_known(tmp_db, monkeypatch):
    with _session() as session:
        project = Project(name="g", path="/g", language="python")
        session.add(project)
        session.flush()
        existing = GitCommit(
            project_id=project.id, hash="a" * 40, message="old", author="me"
        )
        session.add(existing)
        session.commit()
        project_id = project.id

    output = (
        "a" * 40
        + "|me|2024-08-01T10:00:00Z|old\n"
        + "b" * 40
        + "|you|2024-08-02T10:00:00Z|new\n"
    )
    monkeypatch.setattr(
        git_history,
        "run_command",
        lambda *args, **kwargs: SimpleNamespace(exit_code=0, stdout=output, stderr=""),
    )
    with _session() as session:
        saved = git_history.GitHistoryService(session).analyze_history(
            session.get(Project, project_id)
        )
        assert [c.message for c in saved] == ["new"]


def test_analyze_history_git_failure(tmp_db, monkeypatch):
    with _session() as session:
        project = Project(name="t", path="/t", language="python")
        session.add(project)
        session.commit()
        project_id = project.id

    monkeypatch.setattr(
        git_history,
        "run_command",
        lambda *a, **k: SimpleNamespace(exit_code=128, stdout="", stderr="fatal"),
    )
    with _session() as session:
        assert (
            git_history.GitHistoryService(session).analyze_history(
                session.get(Project, project_id)
            )
            == []
        )


def test_git_get_project_unknown(tmp_db):
    with pytest.raises(ValueError):
        with _session() as session:
            git_history.GitHistoryService.get_project(session, "missing")
