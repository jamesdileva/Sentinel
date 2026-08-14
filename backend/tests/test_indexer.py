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
