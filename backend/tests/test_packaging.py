"""Sprint 15: packaging scripts validation (scripts/build.py, release.py, run.py).

These tests exercise the pure, deterministic parts of the build/release/run
helpers without invoking npm, uvicorn, or Task Scheduler.
"""

import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import build  # noqa: E402
import release  # noqa: E402


def test_release_collects_core_files():
    files = release._collect_files()
    rel = {f.relative_to(REPO_ROOT).as_posix() for f in files}
    assert "run.py" in rel
    assert "scripts/install_service.py" in rel
    assert "scripts/build.py" in rel
    assert ".env.example" in rel
    assert "backend/pyproject.toml" in rel
    assert any(p.startswith("docs/") for p in rel)
    assert "docker-compose.yml" not in rel


def test_release_collects_backend_source_but_no_venv():
    files = release._collect_files()
    rel = {f.relative_to(REPO_ROOT).as_posix() for f in files}
    assert "backend/app/main.py" in rel
    assert not any(".venv" in p for p in rel)


def test_release_excludes_runtime_data():
    files = release._collect_files()
    assert all(
        not f.relative_to(REPO_ROOT).as_posix().startswith("data/") for f in files
    )


def test_release_make_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "ROOT", tmp_path)
    (tmp_path / "dist").mkdir()
    (tmp_path / "run.py").write_text("#!/usr/bin/env python\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("# env", encoding="utf-8")
    monkeypatch.setattr(release, "INCLUDED", ["run.py", ".env.example"])
    archive, checksums = release.make_archive()
    assert archive.exists()
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert any(n.endswith("run.py") for n in names)
    assert "run.py" in checksums
    assert len(checksums["run.py"]) == 64


def test_release_dry_run_no_output(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "ROOT", tmp_path)
    assert release.main(["--dry-run"]) == 0
    assert not (tmp_path / "dist").exists()


def test_build_parser_flags():
    parser = build.build_parser()
    args = parser.parse_args(["--dist"])
    assert args.dist is True
    assert args.skip_tests is False
    args2 = parser.parse_args(["--skip-tests"])
    assert args2.skip_tests is True


def test_run_parser_flags():
    import run

    parser = run.build_parser()
    args = parser.parse_args(["--check"])
    assert args.check is True
    assert args.port == 8000
    assert run.port_taken(59999) is False


def test_run_requires_python311():
    import run

    assert run.PYTHON_MIN >= (3, 11)
    assert run.ROOT == REPO_ROOT
