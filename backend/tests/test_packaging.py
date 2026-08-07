"""Sprint 12: packaging scripts validation (scripts/build.py, release.py).

These tests exercise the pure, deterministic parts of the build/release
helpers without invoking Docker or npm.
"""

import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build  # noqa: E402
import release  # noqa: E402


def test_release_collects_core_files():
    files = release._collect_files()
    rel = {f.relative_to(REPO_ROOT).as_posix() for f in files}
    assert "docker-compose.yml" in rel
    assert "docker-compose.dev.yml" in rel
    assert "docker/backend/Dockerfile" in rel
    assert "docker/frontend/Dockerfile" in rel
    assert "docker/nginx.conf" in rel
    assert ".env.example" in rel
    assert any(p.startswith("docs/") for p in rel)


def test_release_excludes_runtime_data(tmp_path, monkeypatch):
    files = release._collect_files()
    assert all("data/" not in f.relative_to(REPO_ROOT).as_posix() for f in files)


def test_release_make_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "ROOT", tmp_path)
    (tmp_path / "dist").mkdir()
    (tmp_path / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
    (tmp_path / ".env.example").write_text("# env", encoding="utf-8")
    monkeypatch.setattr(release, "INCLUDED", ["docker-compose.yml", ".env.example"])
    archive, checksums = release.make_archive()
    assert archive.exists()
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert any(n.endswith("docker-compose.yml") for n in names)
    assert "docker-compose.yml" in checksums
    assert len(checksums["docker-compose.yml"]) == 64


def test_release_dry_run_no_output(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "ROOT", tmp_path)
    assert release.main(["--dry-run"]) == 0
    assert not (tmp_path / "dist").exists()


def test_build_parser_flags():
    parser = build.build_parser()
    args = parser.parse_args(["--backend"])
    assert args.backend is True
    assert args.frontend is False
    args2 = parser.parse_args(["--skip-tests"])
    assert args2.skip_tests is True
    args3 = parser.parse_args(["--test"])
    assert args3.test_only is True
