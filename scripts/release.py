#!/usr/bin/env python
"""Project Sentinel — release helper (Sprint 12, docs/02 §12.5).

Produces a versioned release archive a human can ship to the laptop server:

    dist/sentinel-<version>.zip
    dist/sentinel-<version>.sha256  (per-file manifest)

The archive contains the compose file, env example, Dockerfiles, nginx config,
docs, and backend packaging metadata — everything needed to run `docker compose
up` on a fresh machine. It deliberately omits runtime `data/`, secrets, and
venvs (they live on each host, per docs/01 Rule 1).

Usage:
    python scripts/release.py                 # build dist/sentinel-0.1.0.zip
    python scripts/release.py --tag           # also create a git tag v0.1.0
    python scripts/release.py --dry-run       # print the plan, write nothing
"""

import argparse
import datetime
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BACKEND_APP = ROOT / "backend" / "app"
if sys.path and str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app import __version__ as VERSION  # noqa: E402

INCLUDED = [
    "docker-compose.yml",
    "docker-compose.dev.yml",
    "docker/backend/Dockerfile",
    "docker/frontend/Dockerfile",
    "docker/nginx.conf",
    ".env.example",
    "docs",
    "backend/pyproject.toml",
]


def _collect_files() -> list[Path]:
    files: list[Path] = []
    for entry in INCLUDED:
        path = ROOT / entry
        if path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file())
        elif path.exists():
            files.append(path)
    return files


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_archive() -> tuple[Path, dict[str, str]]:
    """Stage the release tree, zip it, and return (archive, checksum map)."""
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    release = f"sentinel-{VERSION}"
    archive = dist / f"{release}.zip"
    checksums: dict[str, str] = {}

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / release
        for source in _collect_files():
            rel = source.relative_to(ROOT)
            target = staging / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(staging.rglob("*")):
                if file.is_file():
                    zf.write(file, file.relative_to(tmp))
        for source in _collect_files():
            rel = source.relative_to(ROOT)
            checksums[str(rel).replace("\\", "/")] = _sha256(source)
    return archive, checksums


def write_manifest(archive: Path, checksums: dict[str, str]) -> Path:
    manifest = archive.with_suffix(".sha256")
    lines = "\n".join(
        f"{digest}  {name}" for name, digest in sorted(checksums.items())
    )
    manifest.write_text(lines + "\n", encoding="utf-8")
    return manifest


def append_changelog() -> None:
    """Add a release heading to docs/03 §Changelog so provenance stays in-repo."""
    changelog = ROOT / "docs" / "03_Sprint_Plan.md"
    if not changelog.exists():
        return
    heading = f"### Release {VERSION} ({datetime.date.today().isoformat()})"
    content = changelog.read_text(encoding="utf-8")
    if heading in content:
        return
    marker = "## Changelog"
    content = content.replace(marker, f"{marker}\n\n{heading}\n- ", 1)
    changelog.write_text(content, encoding="utf-8")


def git_tag() -> int:
    tag = f"v{VERSION}"
    return subprocess.run(["git", "tag", tag], cwd=ROOT).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="release.py", description=__doc__)
    parser.add_argument(
        "--tag", action="store_true", help="Create a git tag v<version>"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the file plan without writing any artifact",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    files = _collect_files()

    print(f"Releasing sentinel-{VERSION} ({len(files)} files)")
    for rel in sorted(f.relative_to(ROOT) for f in files):
        print(f"  {rel.as_posix()}")

    if args.dry_run:
        return 0

    archive, checksums = make_archive()
    manifest = write_manifest(archive, checksums)
    append_changelog()
    print(f"Wrote {archive.relative_to(ROOT)}")
    print(f"Wrote {manifest.relative_to(ROOT)}")

    if args.tag:
        return git_tag()
    return 0


if __name__ == "__main__":
    sys.exit(main())