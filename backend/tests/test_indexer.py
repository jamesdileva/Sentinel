"""Sprint 3: IndexerService acceptance tests."""

from pathlib import Path

from sqlmodel import Session

from app.db import connection
from app.repositories import ProjectFileRepository
from app.services.indexer import IndexerService

FIXTURES = Path(__file__).parent / "fixtures"
PY_PROJECT = FIXTURES / "sample_python_project"
REACT_PROJECT = FIXTURES / "sample_react_project"


def _service(tmp_db) -> IndexerService:
    return IndexerService(Session(connection.get_engine()))


def test_detect_language(tmp_db):
    svc = _service(tmp_db)
    assert svc.detect_language(PY_PROJECT) == "python"
    assert svc.detect_language(REACT_PROJECT) == "typescript"


def test_detect_framework(tmp_db):
    svc = _service(tmp_db)
    assert svc.detect_framework(PY_PROJECT) == "fastapi"
    assert svc.detect_framework(REACT_PROJECT) == "react"


def test_extract_dependencies_python(tmp_db):
    svc = _service(tmp_db)
    deps = svc.extract_dependencies(PY_PROJECT)
    names = {d.name for d in deps}
    assert {"fastapi", "uvicorn", "sqlmodel"} <= names
    assert all(d.type == "production" for d in deps)


def test_extract_dependencies_react(tmp_db):
    svc = _service(tmp_db)
    deps = svc.extract_dependencies(REACT_PROJECT)
    by_name = {d.name: d for d in deps}
    assert by_name["react"].type == "production"
    assert by_name["typescript"].type == "dev"


def test_extract_dependencies_python_deduplicated(tmp_db):
    svc = _service(tmp_db)
    deps = svc.extract_dependencies(PY_PROJECT)
    by_name = {d.name: d for d in deps}
    assert by_name["fastapi"].version == "0.110.0"
    assert by_name["uvicorn"].version == "0.29.0"
    assert len(by_name) == len(deps)


def test_extract_build_commands_python(tmp_db):
    svc = _service(tmp_db)
    commands = svc.extract_build_commands(PY_PROJECT)
    assert commands["test"] == "pytest"
    assert commands["install"] == "pip install -r requirements.txt"
    assert "startup" in commands


def test_extract_build_commands_react(tmp_db):
    svc = _service(tmp_db)
    commands = svc.extract_build_commands(REACT_PROJECT)
    assert commands["install"] == "npm install"
    assert commands["build"] == "tsc -b && vite build"
    assert commands["test"] == "vitest run"
    assert commands["startup"] == "vite"


def test_index_project_creates_entries(tmp_db):
    svc = _service(tmp_db)
    project = svc.index_project(PY_PROJECT)

    assert project.id is not None
    assert project.language == "python"
    assert project.framework == "fastapi"
    assert project.last_indexed is not None

    files = ProjectFileRepository(Session(connection.get_engine())).get_by_project(
        project.id
    )
    rel_paths = {f.path for f in files}
    assert "app/main.py" in rel_paths
    assert "app/services/__init__.py" in rel_paths

    deps = project.dependencies
    assert {d.name for d in deps} >= {"fastapi"}


def test_index_project_idempotent(tmp_db):
    svc = _service(tmp_db)
    first = svc.index_project(PY_PROJECT)
    second = svc.index_project(PY_PROJECT)
    assert first.id == second.id

    session = Session(connection.get_engine())
    count = len(ProjectFileRepository(session).get_by_project(first.id))
    assert count == len(ProjectFileRepository(session).get_by_project(second.id))


def test_reindex_project(tmp_db):
    svc = _service(tmp_db)
    project = svc.index_project(PY_PROJECT)
    again = svc.reindex_project(project.id)
    assert again.id == project.id
    assert again.language == "python"


def test_scan_all_projects_discovers_fixtures(tmp_db):
    svc = _service(tmp_db)
    projects = svc.scan_all_projects([str(FIXTURES)])
    names = {p.name for p in projects}
    assert "Sample Python Project" in names
    assert "Sample React Project" in names


def test_update_incremental_only_changes_files(tmp_db):
    svc = _service(tmp_db)
    project = svc.index_project(PY_PROJECT)
    before = len(
        ProjectFileRepository(Session(connection.get_engine())).get_by_project(
            project.id
        )
    )

    new_file = PY_PROJECT / "app" / "extra.py"
    new_file.write_text("def helper():\n    return 1\n", encoding="utf-8")
    try:
        processed = svc.update_incremental(project.id, ["app/extra.py", "app/main.py"])
        assert processed == 2
        files = ProjectFileRepository(Session(connection.get_engine())).get_by_project(
            project.id
        )
        assert len(files) == before + 1
        assert {f.path for f in files} >= {"app/extra.py"}
    finally:
        new_file.unlink()


def test_index_project_survives_non_utf8_requirements(tmp_db, tmp_path):
    """Sprint 12.2 regression: latin-1 requirements.txt must not abort indexing.

    MLBattles' requirements.txt contained non-UTF-8 bytes; the framework
    detector read it with strict UTF-8 and raised UnicodeDecodeError, killing
    index_project for the whole repo.
    """
    repo = tmp_path / "mlbattles"
    repo.mkdir()
    (repo / "train.py").write_text("import gym\n", encoding="utf-8")
    (repo / "requirements.txt").write_bytes(
        b"gymnasium\r\npygame\r\n" + b"\x93curly quote in a comment\x94\r\n"
    )
    svc = _service(tmp_db)
    project = svc.index_project(repo)
    assert project.language == "python"
    assert project.framework is None  # latin-1 line does not match any framework
    commands = svc.extract_build_commands(repo)
    assert commands["install"] == "pip install -r requirements.txt"
    deps = svc.extract_dependencies(repo)
    assert {d.name for d in deps} >= {"gymnasium", "pygame"}
