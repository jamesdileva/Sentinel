"""Sprint 3: IndexerService acceptance tests."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.db import connection
from app.db.models import ChatMessage, Dependency, Project, ProjectFile
from app.repositories import ProjectFileRepository
from app.services.indexer import (
    IndexerService,
    is_sync_owned,
    origin_url,
)

FIXTURES = Path(__file__).parent / "fixtures"
PY_PROJECT = FIXTURES / "sample_python_project"
REACT_PROJECT = FIXTURES / "sample_react_project"


def _service(tmp_db) -> IndexerService:
    return IndexerService(Session(connection.get_engine()))


def _checkout(
    root: Path,
    *parts: str,
    url: str | None = None,
    files: dict[str, str] | None = None,
) -> Path:
    """Create a checkout-shaped dir: `.git/` (optionally with an origin URL
    config) and optional source files."""
    checkout = root.joinpath(*parts)
    (checkout / ".git").mkdir(parents=True)
    if url is not None:
        (checkout / ".git" / "config").write_text(
            f'[remote "origin"]\n\turl = {url}\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n',
            encoding="utf-8",
        )
    for name, content in (files or {}).items():
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return checkout


def _seed_project(tmp_path, project_id: str, name: str, rel_path: str, tmp_db) -> None:
    with Session(connection.get_engine()) as session:
        session.add(
            Project(
                id=project_id,
                name=name,
                path=str(Path(tmp_path) / rel_path),
                language="python",
            )
        )
        session.commit()


def test_detect_language(tmp_db):
    svc = _service(tmp_db)
    assert svc.detect_language(PY_PROJECT) == "python"
    assert svc.detect_language(REACT_PROJECT) == "typescript"


def test_discover_prunes_noise_dirs(tmp_db, tmp_path):
    """v1.17.7: a home-dir watch root (AppData, OneDrive, node_modules,
    .venv, ...) never descends into noise — those cannot hold sync-owned
    checkouts, and the old rglob walk visited every file under them."""
    _checkout(tmp_path, "real-proj", url="https://github.com/o/real-proj.git")
    _checkout(tmp_path, "AppData", "Local", "noise-repo")
    _checkout(tmp_path, "OneDrive", "Desktop", "backup-repo")
    _checkout(tmp_path, "node_modules", "dep-repo")
    _checkout(tmp_path, ".venv", "site-packages", "embedded-repo")
    _checkout(tmp_path, ".codex", "memories", "agent-repo")
    svc = _service(tmp_db)
    found = [
        p.relative_to(tmp_path).as_posix() for p in svc.discover_repositories(tmp_path)
    ]
    assert found == ["real-proj"]


def test_discover_is_case_insensitive_on_noise_dirs(tmp_db, tmp_path):
    _checkout(tmp_path, "keep", url="https://github.com/o/keep.git")
    _checkout(tmp_path, "APPData", "nested", "repo")
    _checkout(tmp_path, "Node_Modules", "x", "repo")
    svc = _service(tmp_db)
    found = [
        p.relative_to(tmp_path).as_posix() for p in svc.discover_repositories(tmp_path)
    ]
    assert found == ["keep"]


def test_discover_respects_depth_boundary(tmp_db, tmp_path):
    """v1.17.7: checkouts at depth <= _DISCOVERY_DEPTH are found, deeper
    trees are never entered (the old rglob only *filtered* at depth)."""
    _checkout(tmp_path, "a", "b", "c", "repo")  # depth 4 -> found
    _checkout(tmp_path, "x", "y", "z", "q", "repo")  # depth 5 -> not found
    svc = _service(tmp_db)
    found = sorted(
        p.relative_to(tmp_path).as_posix() for p in svc.discover_repositories(tmp_path)
    )
    assert found == ["a/b/c/repo"]


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


@pytest.mark.parametrize(
    "files,expected",
    [
        ({"Makefile": "build:\n\tgcc main.c\n"}, {"build": "make build"}),
        ({"Makefile": "all:\n\tgcc main.c\n"}, {"build": "make all"}),
        (
            {"Makefile": "build:\n\tgcc main.c\ntest:\n\t./run_tests\n"},
            {"build": "make build", "test": "make test"},
        ),
        (
            {"Cargo.toml": "[package]\nname = 'x'\n"},
            {"build": "cargo build", "test": "cargo test"},
        ),
        (
            {"go.mod": "module example.com/x\n"},
            {"build": "go build ./...", "test": "go test ./..."},
        ),
        ({"pom.xml": "<project/>"}, {"build": "mvn package", "test": "mvn test"}),
        (
            {"app.csproj": "<Project/>"},
            {"build": "dotnet build", "test": "dotnet test"},
        ),
        ({"app.sln": ""}, {"build": "dotnet build", "test": "dotnet test"}),
        (
            {"build.gradle": "tasks {}\n"},
            {"build": "gradle build", "test": "gradle test"},
        ),
        (
            {"CMakeLists.txt": "cmake_minimum_required(VERSION 3.15)\n"},
            {"build": "cmake --build build"},
        ),
        (
            {
                "CMakeLists.txt": (
                    "cmake_minimum_required(VERSION 3.15)\n" "enable_testing()\n"
                )
            },
            {"build": "cmake --build build", "test": "ctest --test-dir build"},
        ),
        (
            {
                "CMakeLists.txt": (
                    "cmake_minimum_required(VERSION 3.15)\n"
                    "add_test(NAME smoke COMMAND trader)\n"
                )
            },
            {"build": "cmake --build build", "test": "ctest --test-dir build"},
        ),
    ],
)
def test_extract_build_commands_new_manifests(tmp_path, files, expected):
    """v1.17.7.5: Makefile, Cargo, go, Maven, dotnet and Gradle projects all
    get deterministic build/test commands."""
    root = tmp_path / "manifest-project"
    root.mkdir()
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")
    from app.utils.command_extractor import extract_build_commands

    commands = extract_build_commands(root)
    for key, value in expected.items():
        assert commands[key] == value, f"{key} mismatch: {commands}"


def test_extract_build_commands_from_readme(tmp_path):
    """v1.17.7.5: build commands documented in READMEs are discovered —
    the user's ask: "find it better in the docs if there is one"."""
    root = tmp_path / "readme-project"
    root.mkdir()
    (root / "README.md").write_text(
        "# App\n\n## Build\n\n```bash\nnpm run build\n```\n", encoding="utf-8"
    )
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["build"] == "npm run build"


def test_extract_build_commands_from_readme_plain_line(tmp_path):
    root = tmp_path / "readme-project"
    root.mkdir()
    (root / "README.md").write_text(
        "# App\nTo build this project run make build first.\n", encoding="utf-8"
    )
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["build"] == "make build"


def test_extract_build_commands_readme_does_not_invent(tmp_path):
    """Only known spellings are accepted — arbitrary doc lines never become
    commands (Rule 3: determinism)."""
    root = tmp_path / "readme-project"
    root.mkdir()
    (root / "README.md").write_text(
        "# App\nRun my magic compile-step, then deploy to the cloud.\n",
        encoding="utf-8",
    )
    from app.utils.command_extractor import extract_build_commands

    commands = extract_build_commands(root)
    assert commands["build"] == ""
    assert commands["test"] == ""


def test_extract_build_commands_manifest_beats_readme(tmp_path):
    """Explicit package.json scripts win over README prose."""
    root = tmp_path / "manifest-readme-project"
    root.mkdir()
    (root / "package.json").write_text(
        '{"scripts": {"build": "tsc -b && vite build"}}', encoding="utf-8"
    )
    (root / "README.md").write_text("Run npm run build.\n", encoding="utf-8")
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["build"] == "tsc -b && vite build"


def test_extract_build_commands_from_agents_md_fenced(tmp_path):
    """v1.17.7.7: AGENTS.md commands inside fenced code blocks are accepted
    (the AGENTS.md candidate is scoped to code fences)."""
    root = tmp_path / "agents-project"
    root.mkdir()
    (root / "AGENTS.md").write_text(
        "# Convention\n\nInstructions live in fences:\n\n```bash\npytest\n```\n",
        encoding="utf-8",
    )
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["test"] == "pytest"


def test_extract_build_commands_from_agents_md_ignores_prose(tmp_path):
    """v1.17.7.7: a mid-sentence mention like Sentinel's own AGENTS.md
    ("`pytest` in `backend/`") must NOT mint a command — no fences, no
    match. AG's AGENTS.md (a session log with zero command literals) is
    the real-world case this guards."""
    root = tmp_path / "agents-prose-project"
    root.mkdir()
    (root / "AGENTS.md").write_text(
        "# Notes\nRun all existing tests before committing (`pytest` in "
        "`backend/`). UV seams and normal maps are the weakest part.\n",
        encoding="utf-8",
    )
    from app.utils.command_extractor import extract_build_commands

    commands = extract_build_commands(root)
    assert commands["test"] == ""


def test_extract_build_commands_pytest_convention(tmp_path):
    """v1.17.7.7: a repo with a root `tests/` dir and root-level Python
    files gets test: pytest by deterministic convention (AG: no manifest,
    only tests/ + sf3d_worker.py)."""
    root = tmp_path / "py-convention"
    root.mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "test_thing.py").write_text("def test_x():\n    pass\n")
    (root / "worker.py").write_text("print('hi')\n")
    from app.utils.command_extractor import extract_build_commands

    commands = extract_build_commands(root)
    assert commands["test"] == "pytest"
    assert commands["build"] == ""


def test_extract_build_commands_pytest_convention_requires_python(tmp_path):
    """v1.17.7.7: a tests/ dir alone is not a pytest signal — a C++ repo
    with tests/ but no root-level .py files gets nothing."""
    root = tmp_path / "cpp-convention"
    root.mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "test_main.cpp").write_text("int main() {}\n")
    (root / "main.cpp").write_text("int main() {}\n")
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["test"] == ""


def test_extract_build_commands_pytest_uses_project_venv(tmp_path):
    """v1.17.7.7: a repo that owns a .venv-style interpreter gets its own
    python -m pytest instead of a bare `pytest` that may not exist on the
    global PATH (AG: .venv_sf3d with pytest 9.1.1)."""
    root = tmp_path / "venv-convention"
    root.mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "test_thing.py").write_text("def test_x():\n    pass\n")
    (root / "worker.py").write_text("print('hi')\n")
    venv = root / ".venv_sf3d" / "Scripts"
    venv.mkdir(parents=True)
    (venv / "python.exe").write_text("dummy")
    from app.utils.command_extractor import extract_build_commands

    command = extract_build_commands(root)["test"]
    assert command.endswith('python.exe" -m pytest')
    assert ".venv_sf3d" in command


def test_extract_build_commands_pytest_venv_skips_nested_python(tmp_path):
    """The venv must sit at the project root — a random Scripts/python.exe
    deep in the tree is not the project's interpreter."""
    root = tmp_path / "nested-python"
    root.mkdir()
    (root / "tests").mkdir()
    (root / "worker.py").write_text("print('hi')\n")
    deep = root / "tools" / "Scripts"
    deep.mkdir(parents=True)
    (deep / "python.exe").write_text("dummy")
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["test"] == "pytest"


# --- v1.17.8.0: subdir manifests, CLI entry points, startup discovery -------


def test_extract_build_commands_subdir_npm(tmp_path):
    """v1.17.8.0: an app one level down (CG's renderer/) is discovered from
    its package.json and prefixed with `cd <dir> &&`."""
    root = tmp_path / "cg-like"
    root.mkdir()
    renderer = root / "renderer"
    renderer.mkdir()
    (renderer / "package.json").write_text(
        '{"scripts": {"build": "npm run build:electron && vite build", '
        '"start": "concurrently \\"backend\\" \\"electron\\""}}',
        encoding="utf-8",
    )
    from app.utils.command_extractor import extract_build_commands

    commands = extract_build_commands(root)
    assert commands["install"] == "cd renderer && npm install"
    assert commands["build"] == "cd renderer && npm run build"
    assert commands["startup"] == "cd renderer && npm run start"


def test_extract_build_commands_subdir_npm_prefers_start_over_dev(tmp_path):
    root = tmp_path / "app-dir"
    root.mkdir()
    frontend = root / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text(
        '{"scripts": {"dev": "vite", "build": "tsc -b && vite build"}}',
        encoding="utf-8",
    )
    from app.utils.command_extractor import extract_build_commands

    commands = extract_build_commands(root)
    assert commands["startup"] == "cd frontend && npm run dev"
    assert commands["build"] == "cd frontend && npm run build"


def test_extract_build_commands_subdir_pip(tmp_path):
    """backend/requirements.txt -> cd backend && pip install (CG, demake)."""
    root = tmp_path / "backend-pip"
    root.mkdir()
    (root / "backend").mkdir()
    (root / "backend" / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["install"] == (
        "cd backend && pip install -r requirements.txt"
    )


def test_extract_build_commands_root_manifest_beats_subdir(tmp_path):
    """A root package.json always wins over a subdir one (no cd needed)."""
    root = tmp_path / "root-wins"
    root.mkdir()
    (root / "package.json").write_text(
        '{"scripts": {"build": "tsc -b && vite build"}}', encoding="utf-8"
    )
    (root / "renderer").mkdir()
    (root / "renderer" / "package.json").write_text(
        '{"scripts": {"build": "vite build"}}', encoding="utf-8"
    )
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["build"] == "tsc -b && vite build"


def test_extract_build_commands_python_cli_gui(tmp_path):
    """v1.17.8.0: an argparse `gui` subcommand in a package entry module is
    a code-defined launchable app (AG: `python -m rigging_engine.main gui`)."""
    root = tmp_path / "gui-app"
    root.mkdir()
    pkg = root / "rigging_engine"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "main.py").write_text(
        "import argparse\n"
        'sub = parser.add_subparsers(dest="command")\n'
        'sub.add_parser("gui", help="Launch the graphical application")\n',
        encoding="utf-8",
    )
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["startup"] == (
        "python -m rigging_engine.main gui"
    )


def test_extract_build_commands_python_cli_web_root_file(tmp_path):
    """A root-level app.py with a `web` subcommand -> python app.py web."""
    root = tmp_path / "web-app"
    root.mkdir()
    (root / "app.py").write_text(
        "import argparse\n"
        "sub = parser.add_subparsers()\n"
        'sub.add_parser("web", help="Serve the web demo")\n',
        encoding="utf-8",
    )
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["startup"] == "python app.py web"


def test_extract_build_commands_python_cli_requires_argparse(tmp_path):
    """Prose like `main gui` in a docstring must not mint a command."""
    root = tmp_path / "no-cli"
    root.mkdir()
    pkg = root / "mylib"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "main.py").write_text(
        "# run with: python -m mylib.main gui\n", encoding="utf-8"
    )
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["startup"] == ""


def test_extract_build_commands_entry_uvicorn(tmp_path):
    """v1.17.8.0: an entry module that documents `uvicorn main:app` is a
    service (demake's backend/main.py: "Run with: uvicorn main:app
    --reload")."""
    root = tmp_path / "fastapi-app"
    root.mkdir()
    (root / "backend").mkdir()
    (root / "backend" / "main.py").write_text(
        '"""Entry point. Run with: uvicorn main:app --reload"""\n'
        "from fastapi import FastAPI\n",
        encoding="utf-8",
    )
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["startup"] == (
        "cd backend && uvicorn main:app --reload"
    )


def test_extract_build_commands_startup_from_readme(tmp_path):
    """v1.17.8.0: whitelisted startup spellings in docs (AG's USER_GUIDE
    style) are discovered."""
    root = tmp_path / "readme-startup"
    root.mkdir()
    (root / "README.md").write_text(
        "# App\n\nLaunch the web UI:\n\n```bash\npython -m streamlit run "
        "dashboard/app.py\n```\n",
        encoding="utf-8",
    )
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["startup"] == "python -m streamlit run"


def test_extract_build_commands_from_development_md(tmp_path):
    """v1.17.8.0: DEVELOPMENT.md is a doc candidate (CG keeps its Quick
    Start there)."""
    root = tmp_path / "devdoc"
    root.mkdir()
    (root / "DEVELOPMENT.md").write_text(
        "# Setup\n\n```bash\nnpm install\nnpm run build\n```\n", encoding="utf-8"
    )
    from app.utils.command_extractor import extract_build_commands

    commands = extract_build_commands(root)
    assert commands["build"] == "npm run build"
    assert commands["install"] == "npm install"


def test_extract_build_commands_subdir_pytest_convention(tmp_path):
    """v1.17.8.0: backend/tests/ + backend-level .py files -> cd backend
    && pytest (CG)."""
    root = tmp_path / "backend-tests"
    root.mkdir()
    (root / "backend").mkdir()
    (root / "backend" / "tests").mkdir()
    (root / "backend" / "tests" / "test_api.py").write_text("def test_x(): pass\n")
    (root / "backend" / "run.py").write_text("print('hi')\n")
    from app.utils.command_extractor import extract_build_commands

    assert extract_build_commands(root)["test"] == "cd backend && pytest"


def test_extract_build_commands_venv_plain_name(tmp_path):
    """v1.17.8.0: a plain `venv/` dir (not .venv*) is a repo venv — CG and
    demake both use it — and qualifies the test command."""
    root = tmp_path / "plain-venv"
    root.mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "test_thing.py").write_text("def test_x(): pass\n")
    (root / "worker.py").write_text("print('hi')\n")
    venv = root / "venv" / "Scripts"
    venv.mkdir(parents=True)
    (venv / "python.exe").write_text("dummy")
    from app.utils.command_extractor import extract_build_commands

    command = extract_build_commands(root)["test"]
    assert command.endswith('python.exe" -m pytest')
    assert "venv" in command


def test_extract_build_commands_subdir_pytest_uses_venv(tmp_path):
    """A cd-prefixed pytest also gets the repo venv (CG end-to-end)."""
    root = tmp_path / "cg-venv"
    root.mkdir()
    (root / "backend").mkdir()
    (root / "backend" / "tests").mkdir()
    (root / "backend" / "tests" / "test_api.py").write_text("def test_x(): pass\n")
    (root / "backend" / "run.py").write_text("print('hi')\n")
    venv = root / "venv" / "Scripts"
    venv.mkdir(parents=True)
    (venv / "python.exe").write_text("dummy")
    from app.utils.command_extractor import extract_build_commands

    command = extract_build_commands(root)["test"]
    assert command.startswith("cd backend && ")
    assert command.endswith('python.exe" -m pytest')


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


def test_reindex_preserves_embedding_ids(tmp_db):
    """v1.17.2: a re-scan must not null out knowledge bookkeeping. Rows keep
    their id (Chroma doc ids are the row ids) and their `embedding_id`, so
    the incremental knowledge index skips already-embedded files instead of
    re-embedding the whole project after every restart."""
    svc = _service(tmp_db)
    project = svc.index_project(PY_PROJECT)
    session = Session(connection.get_engine())
    files = ProjectFileRepository(session).get_by_project(project.id)
    assert files
    ids = {f.id for f in files}
    marked = files[0]
    marked.embedding_id = marked.id
    session.commit()

    again = svc.index_project(project.path)
    assert again.id == project.id
    refiles = ProjectFileRepository(Session(connection.get_engine())).get_by_project(
        project.id
    )
    assert {f.id for f in refiles} == ids
    by_path = {f.path: f for f in refiles}
    assert by_path[marked.path].embedding_id == marked.id


def test_reindex_drops_vanished_files(tmp_db, tmp_path):
    svc = _service(tmp_db)
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")
    (repo / "src" / "b.py").write_text("print('b')\n", encoding="utf-8")
    project = svc.index_project(repo)
    (repo / "src" / "b.py").unlink()
    svc.index_project(project.path)
    paths = {
        f.path
        for f in ProjectFileRepository(Session(connection.get_engine())).get_by_project(
            project.id
        )
    }
    assert paths == {"src/a.py"}


def test_scan_all_projects_discovers_sync_owned_checkouts(tmp_db, tmp_path):
    """v1.17.5: discovery indexes only sync-owned checkouts under a watch
    root — a canonical `owner/name` clone and a flat adopted checkout —
    never worktrees, copies or origin-less dirs."""
    svc = _service(tmp_db)
    _checkout(
        tmp_path,
        "jamesdileva",
        "python-app",
        url="https://github.com/jamesdileva/python-app.git",
        files={"app/main.py": "print('hi')\n"},
    )
    _checkout(
        tmp_path,
        "React-App",
        url="https://github.com/jamesdileva/react-app.git",
        files={"src/index.tsx": "export const x = 1\n"},
    )
    _checkout(  # worktree-style: nested under an owner-shaped dir, wrong url
        tmp_path,
        "CG.worktrees",
        "agents-x",
        url="https://github.com/jamesdileva/cg.git",
        files={"a.py": "x=1\n"},
    )
    _checkout(  # stray copy two levels down
        tmp_path,
        "Desktop",
        "airadio",
        url="https://github.com/jamesdileva/airadio.git",
        files={"a.py": "x=1\n"},
    )
    _checkout(tmp_path, "naked", files={"a.py": "x=1\n"})  # no origin remote
    projects = svc.scan_all_projects([str(tmp_path)])
    paths = {p.path for p in projects}
    assert paths == {
        str(tmp_path / "jamesdileva" / "python-app"),
        str(tmp_path / "React-App"),
    }


def test_scan_all_projects_prefers_canonical_over_flat_copy(tmp_db, tmp_path):
    """The same origin twice (flat + nested clone) keeps only the canonical
    nested checkout — the location repo-sync would pull."""
    svc = _service(tmp_db)
    _checkout(
        tmp_path,
        "jamesdileva",
        "app",
        url="https://github.com/jamesdileva/app.git",
        files={"a.py": "x=1\n"},
    )
    _checkout(
        tmp_path,
        "App",
        url="https://github.com/jamesdileva/app.git",
        files={"a.py": "x=1\n"},
    )
    projects = svc.scan_all_projects([str(tmp_path)])
    assert [p.path for p in projects] == [str(tmp_path / "jamesdileva" / "app")]


def test_origin_url_normalizes_variants(tmp_path):
    cases = {
        "https://github.com/jamesdileva/MyApp.git": "github.com/jamesdileva/myapp",
        "http://github.com/jamesdileva/MyApp": "github.com/jamesdileva/myapp",
        "git@github.com:jamesdileva/MyApp.git": "github.com/jamesdileva/myapp",
        "ssh://git@github.com/jamesdileva/x.git": "github.com/jamesdileva/x",
    }
    for idx, (raw, expected) in enumerate(cases.items()):
        checkout = _checkout(tmp_path, f"repo-{idx}", url=raw)
        assert origin_url(checkout) == expected
    bare = _checkout(tmp_path, "bare")  # no .git/config
    assert origin_url(bare) is None


def test_is_sync_owned_shape_matrix(tmp_path):
    root = tmp_path
    canonical = _checkout(
        root, "jamesdileva", "app", url="https://github.com/jamesdileva/app.git"
    )
    assert is_sync_owned(canonical, root) is True
    wrong_owner = _checkout(
        root, "other", "app", url="https://github.com/jamesdileva/app.git"
    )
    assert is_sync_owned(wrong_owner, root) is False
    non_github = _checkout(
        root, "jamesdileva", "app2", url="https://gitlab.com/jamesdileva/app2.git"
    )
    assert is_sync_owned(non_github, root) is False
    flat = _checkout(root, "My-App", url="https://github.com/jamesdileva/my-app.git")
    assert is_sync_owned(flat, root) is True
    flat_originless = _checkout(root, "naked", files={"a.py": "x=1\n"})
    assert is_sync_owned(flat_originless, root) is False
    worktree = _checkout(
        root,
        "CG.worktrees",
        "agents-x",
        url="https://github.com/jamesdileva/cg.git",
    )
    assert is_sync_owned(worktree, root) is False
    copy = _checkout(
        root, "Desktop", "app", url="https://github.com/jamesdileva/app.git"
    )
    assert is_sync_owned(copy, root) is False
    deep_nested = _checkout(
        root, "AG", "stable-fast-3d", url="https://github.com/jamesdileva/ag.git"
    )
    assert is_sync_owned(deep_nested, root) is False
    assert is_sync_owned(root, root) is True  # explicit scan target


def test_full_scan_gc_removes_unowned_and_gone_projects(tmp_db, tmp_path, monkeypatch):
    """The startup scan (no explicit dirs) drops rows whose checkouts are
    gone, disqualified (copies/worktrees), outside the watch roots, or a
    same-origin duplicate — keeping exactly the sync-owned set."""
    svc = _service(tmp_db)
    _checkout(
        tmp_path,
        "jamesdileva",
        "kept",
        url="https://github.com/jamesdileva/kept.git",
        files={"a.py": "x=1\n"},
    )
    _checkout(  # same origin one level up: the flat duplicate row
        tmp_path,
        "Kept",
        url="https://github.com/jamesdileva/kept.git",
        files={"a.py": "x=1\n"},
    )
    _checkout(  # disqualified but present on disk (worktree shape)
        tmp_path,
        "CG.worktrees",
        "agents-x",
        url="https://github.com/jamesdileva/cg.git",
    )
    for project_id, name, rel in (
        ("p-kept", "Kept", "jamesdileva/kept"),
        ("p-flat", "Kept Flat", "Kept"),
        ("p-gone", "Gone", "gone/app"),
        ("p-work", "Worktree", "CG.worktrees/agents-x"),
        ("p-legacy", "Legacy", "/data/projects/sample_python_project"),
    ):
        _seed_project(tmp_path, project_id, name, rel, tmp_db)

    monkeypatch.setattr(settings, "watch_dirs", [str(tmp_path)])
    svc.scan_all_projects()
    with Session(connection.get_engine()) as session:
        rows = session.exec(select(Project)).all()
    assert {p.id for p in rows} == {"p-kept"}
    assert {p.path for p in rows} == {str(tmp_path / "jamesdileva" / "kept")}


def test_targeted_scan_never_gc(tmp_db, tmp_path, monkeypatch):
    """Repo-sync's targeted rescans (explicit watch_dirs) must never remove
    projects: they index changed repos only, outside the GC's scope."""
    svc = _service(tmp_db)
    _seed_project(tmp_path, "p-gone", "Gone", "gone/app", tmp_db)
    _checkout(
        tmp_path,
        "jamesdileva",
        "kept",
        url="https://github.com/jamesdileva/kept.git",
        files={"a.py": "x=1\n"},
    )
    svc.scan_all_projects([str(tmp_path)])
    with Session(connection.get_engine()) as session:
        rows = session.exec(select(Project)).all()
    assert "p-gone" in {p.id for p in rows}  # stale row survives targeted scans
    assert str(tmp_path / "jamesdileva" / "kept") in {p.path for p in rows}


def test_gc_cascades_dependent_rows(tmp_db, tmp_path, monkeypatch):
    """Deleting a stale project also removes its files, dependencies, chat
    and security-finding rows (FK-clean, Chroma best-effort)."""
    svc = _service(tmp_db)
    _checkout(
        tmp_path,
        "jamesdileva",
        "kept",
        url="https://github.com/jamesdileva/kept.git",
        files={"a.py": "x=1\n"},
    )
    with Session(connection.get_engine()) as session:
        session.add(
            Project(
                id="p-dead", name="Dead", path=str(tmp_path / "dead"), language="python"
            )
        )
        session.add(
            ProjectFile(id="f1", project_id="p-dead", path="a.py", absolute_path="a.py")
        )
        session.add(
            Dependency(id="d1", project_id="p-dead", name="flask", type="production")
        )
        session.add(ChatMessage(id="c1", project_id="p-dead", role="user", text="hi"))
        session.commit()
    monkeypatch.setattr(settings, "watch_dirs", [str(tmp_path)])
    svc.scan_all_projects()
    with Session(connection.get_engine()) as session:
        assert session.get(Project, "p-dead") is None
        assert session.get(ProjectFile, "f1") is None
        assert session.get(Dependency, "d1") is None
        assert session.get(ChatMessage, "c1") is None


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
        # Both listed files are handled; main.py is unchanged so the
        # v1.17.7.1 mtime fast-path skips its re-read/re-parse internally.
        assert processed == 2
        files = ProjectFileRepository(Session(connection.get_engine())).get_by_project(
            project.id
        )
        assert len(files) == before + 1
        assert {f.path for f in files} >= {"app/extra.py"}
    finally:
        new_file.unlink()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_indexes_tracked_files_only(tmp_db, tmp_path):
    """v1.17.7.3: in a real git checkout the file list comes from
    `git ls-files` — untracked files (`.env` secrets, stray junk) and
    gitignored files never enter the index even though they exist on disk."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (repo / "secret.env").write_text("API_KEY=abc\n", encoding="utf-8")
    (repo / "junk.tmp").write_bytes(b"\x00" * 16)
    (repo / ".gitignore").write_text("junk.tmp\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "main.py", ".gitignore"], check=True)
    svc = _service(tmp_db)
    project = svc.index_project(repo)
    paths = {
        f.path
        for f in ProjectFileRepository(Session(connection.get_engine())).get_by_project(
            project.id
        )
    }
    assert paths == {".gitignore", "main.py"}


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_index_is_complete_across_dirs(tmp_db, tmp_path):
    """v1.17.7.5: the index covers *every* tracked file — docs, backend and
    frontend — not just the root or one language. Regression for "are we
    grabbing the docs + backend/frontend files?"."""
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = [
        "README.md",
        "docs/guide.md",
        "backend/app/main.py",
        "backend/app/services/core.py",
        "frontend/src/App.tsx",
        "frontend/package.json",
        "scripts/build.py",
        ".gitignore",
    ]
    for rel in tracked:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n" if rel.endswith(".py") else "{}", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "init",
        ],
        check=True,
    )
    svc = _service(tmp_db)
    project = svc.index_project(repo)
    with Session(connection.get_engine()) as session:
        indexed = {
            f.path.replace("\\", "/")
            for f in ProjectFileRepository(session).get_by_project(project.id)
        }
    assert indexed == set(
        tracked
    ), f"indexed={indexed} must equal the full git-tracked set"


def test_git_fake_git_dir_falls_back_to_walk(tmp_db, tmp_path):
    """A `.git/` dir without a valid index (test checkouts, interrupted
    clones) is not a working git repo — `ls-files` exits non-zero and the
    walk fallback still indexes the tree."""
    repo = _checkout(tmp_path, "repo", files={"a.py": "x=1\n"})
    svc = _service(tmp_db)
    project = svc.index_project(repo)
    paths = {
        f.path
        for f in ProjectFileRepository(Session(connection.get_engine())).get_by_project(
            project.id
        )
    }
    assert paths == {"a.py"}


def test_index_skips_binary_and_oversized_files(tmp_db, tmp_path, monkeypatch):
    """v1.17.7.1: binary suffixes and files above the size cap are never
    parsed or stored — multi-GB model trees must not bloat the scan."""
    monkeypatch.setattr(settings, "max_file_size_kb", 1)  # 1 KB cap
    repo = tmp_path / "ml-project"
    for rel in ("src", "models/sd15/unet", "assets"):
        (repo / rel).mkdir(parents=True)
    (repo / "src" / "train.py").write_text("import torch\n", encoding="utf-8")
    (repo / "models" / "sd15" / "unet" / "model.onnx").write_text(
        "not really a model", encoding="utf-8"
    )
    (repo / "assets" / "weights.pth").write_bytes(b"\x00" * 64)
    (repo / "src" / "big_output.bin").write_bytes(b"\xff" * 2048)

    svc = _service(tmp_db)
    project = svc.index_project(repo)
    paths = {
        f.path
        for f in ProjectFileRepository(Session(connection.get_engine())).get_by_project(
            project.id
        )
    }
    assert paths == {"src/train.py"}


def test_index_ignores_build_artifact_trees(tmp_db, tmp_path):
    """v1.17.7.2: Unity's regenerable `Library/` cache, electron-builder
    `release/` + `win-unpacked/` output and `*.pdb`/`*.bhc` files (build
    symbols / Burst caches) never enter the file index — the desktop's
    index had swollen to 47k files, 25.6k of them Khd4's Unity cache."""
    repo = tmp_path / "game"
    for rel in (
        "Assets/Scripts",
        "Library/PackageCache/com.unity.test/package",
        "Library/BurstCache",
        "Packages/com.vendor.foo",
        "release/win-unpacked/resources/app",
    ):
        (repo / rel).mkdir(parents=True)
    (repo / "Assets" / "Scripts" / "Player.cs").write_text(
        "class Player {}\n", encoding="utf-8"
    )
    (
        repo / "Library" / "PackageCache" / "com.unity.test" / "package" / "index.json"
    ).write_text("{}", encoding="utf-8")
    (repo / "Library" / "BurstCache" / "splat.bhc").write_bytes(b"\x00" * 16)
    (repo / "Packages" / "com.vendor.foo" / "manifest.json").write_text(
        "{}", encoding="utf-8"
    )
    (repo / "release" / "win-unpacked" / "resources" / "app" / "main.js").write_text(
        "module.exports = 1\n", encoding="utf-8"
    )
    (repo / "Assets" / "Scripts" / "Player.pdb").write_bytes(b"\x00" * 16)

    svc = _service(tmp_db)
    project = svc.index_project(repo)
    paths = {
        f.path
        for f in ProjectFileRepository(Session(connection.get_engine())).get_by_project(
            project.id
        )
    }
    assert paths == {
        "Assets/Scripts/Player.cs",
        "Packages/com.vendor.foo/manifest.json",
    }


def test_index_does_not_descend_into_ignored_dirs(tmp_db, tmp_path):
    """v1.17.7.1: ignored directories prune the walk — `node_modules`,
    `.venv*/` (wildcard: catches `.venv_sf3d`) and `data/` are never
    descended into, so their contents produce no rows and no reads."""
    repo = tmp_path / "repo"
    for rel in ("src", "node_modules/pkg", ".venv_sf3d/Lib", "data"):
        (repo / rel).mkdir(parents=True)
    (repo / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (repo / "node_modules" / "pkg" / "index.js").write_text(
        "module.exports = 1\n", encoding="utf-8"
    )
    (repo / ".venv_sf3d" / "Lib" / "torch.dll").write_bytes(b"\x00" * 16)
    (repo / "data" / "state.db").write_bytes(b"\x00" * 16)

    svc = _service(tmp_db)
    project = svc.index_project(repo)
    paths = {
        f.path
        for f in ProjectFileRepository(Session(connection.get_engine())).get_by_project(
            project.id
        )
    }
    assert paths == {"src/main.py"}


def test_mtime_fast_path_skips_reparse(tmp_db, tmp_path, monkeypatch):
    """v1.17.7.1: an unchanged file (same size + mtime) is not re-read or
    re-parsed on a full rescan; a touched file is."""
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")

    calls = []
    import app.services.indexer as indexer_module

    real_parse = indexer_module.parse_file_for_project

    def counting_parse(file_path, language, framework):
        calls.append(Path(file_path).name)
        return real_parse(file_path, language, framework)

    monkeypatch.setattr(indexer_module, "parse_file_for_project", counting_parse)

    svc = _service(tmp_db)
    project = svc.index_project(repo)
    assert calls == ["app.py"]

    calls.clear()
    svc.index_project(project.path)  # untouched -> no parse calls
    assert calls == []

    new_mtime = target.stat().st_mtime_ns + 1_000_000_000
    os.utime(target, ns=(new_mtime, new_mtime))
    svc.index_project(project.path)  # touched -> re-parsed
    assert calls == ["app.py"]


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
