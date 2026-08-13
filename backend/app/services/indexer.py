"""IndexerService — orchestrates repository indexing.

Sprint 3 scope (docs/02 §3.1, docs/03 Sprint 3): deterministic language and
framework detection, file parsing, dependency extraction, and full/incremental
indexing into the knowledge database.
"""

import datetime
import fnmatch
import os
import re
from collections.abc import Callable
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import (
    BuildLog,
    ChatMessage,
    Dependency,
    GitCommit,
    KnowledgeSummary,
    PortfolioScore,
    Project,
    ProjectFile,
    ProjectStatus,
    SecurityFinding,
    TestResult,
)
from app.parsers import parse_file_for_project
from app.repositories import (
    DependencyRepository,
    ProjectFileRepository,
    ProjectRepository,
)
from app.utils import detect_framework, detect_language, extract_build_commands

logger = get_logger(__name__)

_REQUIREMENT_RE = re.compile(
    r"^([A-Za-z0-9_.-]+)\s*(?:==|>=|<=|~=|!=|\^|~)?\s*([^\s#]*)?"
)
_MAX_WALK_DEPTH = 6
_DISCOVERY_DEPTH = 4
# v1.17.7.1: files with these suffixes are never parsed or stored as project
# files — ML model checkpoints, media assets, archives, vendored binaries and
# database files. They are binary, useless for language parsing, and their
# full-content reads dominated the file walk (e.g. a 3.3 GB ONNX model being
# decoded to a multi-GB string on every scan).
_BINARY_SUFFIXES = frozenset(
    {
        ".onnx",
        ".onnx_data",
        ".pt",
        ".pth",
        ".safetensors",
        ".ckpt",
        ".pkl",
        ".pickle",
        ".npy",
        ".npz",
        ".h5",
        ".hdf5",
        ".tflite",
        ".dll",
        ".so",
        ".dylib",
        ".exe",
        ".bin",
        ".dat",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp",
        ".ico",
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".wmv",
        ".webm",
        ".mp3",
        ".wav",
        ".flac",
        ".ogg",
        ".aac",
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".whl",
        ".jar",
        ".pyc",
        ".pyd",
        ".class",
    }
)
# v1.17.7: the watch root defaults to the user's home directory, whose noise
# dirs (AppData, OneDrive, tool caches, vendored deps) would otherwise be
# walked on every full scan. None of these can hold a sync-owned checkout
# (flat direct child or <owner>/<name>), so they are pruned during the walk.
_DISCOVERY_SKIP_DIRS = {
    "appdata",
    "onedrive",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".git",
    "dist",
    "build",
    ".cache",
    ".ollama",
    ".vscode",
    ".config",
    ".codex",
    ".local",
    ".docker",
    ".thumbnails",
    ".copilot",
    ".dotnet",
    ".templateengine",
    ".windows-build-tools",
    ".aws",
    ".claude",
    ".openclaw",
    ".u2net",
    ".vscode-shared",
    ".matplotlib",
    ".runelite",
}


def _pretty_name(directory_name: str) -> str:
    return directory_name.replace("-", " ").replace("_", " ").title()


def origin_url(checkout: Path) -> str | None:
    """Normalized origin URL of a checkout, or None when it has none.

    Normalization mirrors RepoSyncService: lowercased, scheme and `git@`
    stripped, `.git` suffix removed — `https://github.com/O/N.git`,
    `http://github.com/o/n` and `git@github.com:o/n.git` all resolve to
    `github.com/o/n`.
    """
    git_dir = checkout / ".git"
    if not git_dir.is_dir():
        return None
    try:
        lines = (
            (git_dir / "config")
            .read_text(encoding="utf-8", errors="replace")
            .splitlines()
        )
    except OSError:
        return None
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("url = "):
            continue
        url = stripped.removeprefix("url = ").strip().lower()
        return (
            url.removesuffix(".git")
            .replace("git@github.com:", "github.com/")
            .replace("ssh://git@github.com/", "github.com/")
            .removeprefix("https://")
            .removeprefix("http://")
        )
    return None


def is_sync_owned(checkout: Path, watch_root: Path) -> bool:
    """v1.17.5, Rule 5 (projects are known entities): a checkout is a
    project only when repo-sync owns it — i.e. one of two shapes:

    * canonical clone: `<root>/<owner>/<name>` whose origin URL matches
      `github.com/<owner>/<name>` (what RepoSyncService clones and pulls);
    * flat adopted: a direct child of the root with any GitHub origin
      (repos that pre-date the nested layout — repo-sync adopts these via
      `_find_existing_checkout`).

    Git worktrees, stray copies, nested sub-repos and `.codex`-style junk
    are never projects. A checkout passed explicitly as the scan target
    itself (repo-sync's targeted rescans) is always sync-owned.
    """
    try:
        rel = checkout.resolve().relative_to(watch_root.resolve())
    except ValueError:
        return False
    parts = rel.parts
    if not parts:
        return True  # the watch root itself is the intended target
    url = origin_url(checkout)
    if not url or "github.com/" not in url:
        return False
    if len(parts) == 1:
        return True  # flat adopted: any GitHub origin
    if len(parts) == 2:
        owner, name = parts[0], parts[1]
        return url.endswith(f"{owner}/{name}".lower())
    return False


class IndexerService:
    """Deterministic repository scanning and indexing."""

    def __init__(self, session: Session):
        self.session = session
        self.projects = ProjectRepository(session)
        self.files = ProjectFileRepository(session)
        self.dependencies = DependencyRepository(session)

    # --- public API ---------------------------------------------------

    def index_project(self, project_path: str | Path) -> Project:
        """Full index of a single project: detect, parse, store."""
        path = Path(project_path).resolve()
        if not path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        project = self._get_or_create_project(path)
        self._index_files(project)
        self._index_dependencies(project)
        project.language = detect_language(path)
        project.framework = detect_framework(str(path))
        project.stack = {
            "language": project.language,
            "framework": project.framework,
            "commands": extract_build_commands(str(path)),
        }
        project.last_indexed = datetime.datetime.now(datetime.timezone.utc)
        project.status = ProjectStatus.ACTIVE
        self.session.add(project)
        self.session.commit()
        logger.info(
            "Indexed %s (%s, %s)", project.name, project.language, project.framework
        )
        return project

    def reindex_project(self, project_id: str) -> Project:
        """Re-index an existing project (rebuild all derived data)."""
        project = self.projects.get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        return self.index_project(project.path)

    def scan_all_projects(
        self,
        watch_dirs: list[str] | None = None,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> list[Project]:
        """Discover known repositories (.git) under watch dirs and index them.

        v1.17.5: only sync-owned checkouts become projects (see
        `is_sync_owned`); same-origin duplicates keep the canonical nested
        checkout, mirroring RepoSyncService. On the full startup scan (no
        explicit dirs) stale Project rows are garbage-collected; targeted
        rescans from repo-sync never remove projects.

        `progress(done, total, checkout_name)` is called after each checkout
        is indexed (v1.17.7.1: the CLI prints a per-project line so long runs
        don't look frozen).
        """
        dirs = watch_dirs or settings.watch_dirs
        indexed: list[Project] = []
        keep: set[str] = set()
        for watch_dir in dirs:
            watch_root = Path(watch_dir)
            checkouts = self._sync_owned_checkouts(watch_root)
            for index, checkout in enumerate(checkouts, start=1):
                keep.add(self._norm(checkout))
                try:
                    indexed.append(self.index_project(checkout))
                except Exception:
                    logger.exception("Index failed for %s", checkout)
                if progress is not None:
                    progress(index, len(checkouts), checkout.name)
        if watch_dirs is None:
            self._gc_projects(keep)
        return indexed

    def _sync_owned_checkouts(self, watch_root: Path) -> list[Path]:
        """Eligible checkouts under `watch_root`, deduplicated by origin URL.

        A same-origin duplicate (flat copy + canonical clone) keeps only
        the canonical nested checkout — the location repo-sync would use.
        """
        seen: dict[str, Path] = {}
        for checkout in self.discover_repositories(watch_root):
            if not is_sync_owned(checkout, watch_root):
                continue
            url = origin_url(checkout)
            if url is None:
                continue
            current = seen.get(url)
            if current is None:
                seen[url] = checkout
                continue
            parts = checkout.relative_to(watch_root).parts
            if len(parts) == 2 and len(current.relative_to(watch_root).parts) == 1:
                seen[url] = checkout  # canonical nested beats flat copy
        return sorted(seen.values())

    def _gc_projects(self, keep: set[str]) -> None:
        """Drop Project rows not backed by a kept checkout (v1.17.5).

        Removes rows for checkouts that vanished from disk, were never
        sync-owned (worktrees, stray copies, nested sub-repos), live
        outside the watch roots, or duplicate a kept same-origin checkout.
        Cascades files, dependencies, findings, results, summaries, chat,
        portfolio rows and Chroma docs.
        """
        removed = 0
        for project in self.session.exec(select(Project)).all():
            if self._norm(Path(project.path)) in keep:
                continue
            self._delete_project_row(project.id)
            logger.info("GC removed project %s (%s)", project.name, project.path)
            removed += 1
        if removed:
            self.session.commit()
            logger.info("Project GC removed %d stale project(s)", removed)

    @staticmethod
    def _norm(path: Path) -> str:
        return os.path.normcase(str(path.resolve()))

    def _delete_project_row(self, project_id: str) -> None:
        """Remove a project and everything keyed to it (FK-clean)."""
        from sqlmodel import delete

        dependents = (
            ProjectFile,
            Dependency,
            SecurityFinding,
            GitCommit,
            TestResult,
            BuildLog,
            KnowledgeSummary,
            ChatMessage,
            PortfolioScore,
        )
        for model in dependents:
            self.session.exec(delete(model).where(model.project_id == project_id))
        try:
            from app.services.chroma_manager import get_chroma_manager

            get_chroma_manager().delete_by_project(project_id)
        except Exception:  # noqa: BLE001 — Chroma must never block the GC
            logger.debug("Chroma cleanup skipped for project %s", project_id)
        project = self.projects.get(project_id)
        if project is not None:
            self.session.delete(project)
        self.session.flush()

    def discover_repositories(self, watch_dir: str | Path) -> list[Path]:
        """Find directories containing a `.git` folder, depth-limited.

        v1.17.7: an explicit depth-aware walk instead of `rglob("*")` — the
        earlier walk descended into every subdirectory of the watch root
        (e.g. the whole home dir) and only filtered the results; the noisy
        `_DISCOVERY_SKIP_DIRS` are now pruned during the walk, and paths
        beyond `_DISCOVERY_DEPTH` are never entered. Symlinked dirs
        (Windows junctions) are not followed.
        """
        root = Path(watch_dir)
        if not root.is_dir():
            return []
        if (root / ".git").exists():
            return [root]
        repos: list[Path] = []
        stack: list[tuple[Path, int]] = [(root, 0)]
        while stack:
            base, depth = stack.pop()
            if depth >= _DISCOVERY_DEPTH:
                continue
            try:
                with os.scandir(base) as entries:
                    names = list(entries)
            except OSError:
                continue
            for entry in names:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if entry.name.lower() in _DISCOVERY_SKIP_DIRS:
                    continue
                path = Path(entry.path)
                if (path / ".git").exists():
                    repos.append(path)
                stack.append((path, depth + 1))
        return sorted(repos)

    def detect_language(self, project_path: str | Path) -> str:
        return detect_language(project_path)

    def detect_framework(self, project_path: str | Path) -> str | None:
        return detect_framework(project_path)

    def extract_dependencies(self, project_path: str | Path) -> list[Dependency]:
        """Parse dependency manifests into Dependency rows (unpersisted)."""
        path = Path(project_path)
        deps: list[tuple[str, str | None, str]] = []  # (name, version, type)

        requirements = path / "requirements.txt"
        if requirements.exists():
            for line in requirements.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                line = line.strip()
                if not line or line.startswith(("#", "-", "http", "git+")):
                    continue
                match = _REQUIREMENT_RE.match(line)
                if match:
                    deps.append((match.group(1), match.group(2), "production"))

        package_json = path / "package.json"
        if package_json.exists():
            import json

            try:
                data = json.loads(
                    package_json.read_text(encoding="utf-8", errors="replace")
                )
                for name, version in data.get("dependencies", {}).items():
                    deps.append((name, version, "production"))
                for name, version in data.get("devDependencies", {}).items():
                    deps.append((name, version, "dev"))
            except json.JSONDecodeError:
                logger.warning("Invalid package.json at %s", package_json)

        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            text = pyproject.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(
                r'^\s*["\']([^"\']+)["\']\s*[,\]]?\s*$', text, re.MULTILINE
            ):
                raw = match.group(1)
                name = re.split(r"==|>=|<=|~=|!=|!=|<|>|\[|;", raw)[0].strip()
                if name and not name.startswith("python"):
                    deps.append((name, None, "production"))

        # Deduplicate by (name, type), preferring a known version.
        merged: dict[tuple[str, str], Dependency] = {}
        for dep in (Dependency(name=n, version=v, type=t) for n, v, t in set(deps)):
            key = (dep.name, dep.type)
            existing = merged.get(key)
            if existing is None or (
                dep.version is not None and existing.version is None
            ):
                merged[key] = dep
        return sorted(merged.values(), key=lambda d: (d.name, d.type))

    def extract_build_commands(self, project_path: str | Path) -> dict[str, str]:
        return extract_build_commands(project_path)

    def update_incremental(self, project_id: str, changed_files: list[str]) -> int:
        """Re-parse only changed files; return number of files processed."""
        project = self.projects.get(project_id)
        if project is None:
            raise ValueError(f"Unknown project: {project_id}")
        project_root = Path(project.path)
        processed = 0
        for changed in changed_files:
            absolute = (
                Path(changed).resolve()
                if Path(changed).is_absolute()
                else project_root / changed
            )
            if not absolute.exists() or self._is_skippable(
                absolute.relative_to(project_root), absolute
            ):
                continue
            self._upsert_file(project, absolute)
            processed += 1
        self.session.commit()
        return processed

    # --- internals ----------------------------------------------------

    def _get_or_create_project(self, path: Path) -> Project:
        project = self.projects.get_by_path(str(path))
        if project is None:
            project = Project(
                name=_pretty_name(path.name),
                path=str(path),
                language="unknown",
            )
            self.session.add(project)
            self.session.flush()
        return project

    def _is_ignored(self, rel_path: Path) -> bool:
        text = rel_path.as_posix()
        for pattern in settings.ignore_patterns:
            if pattern.endswith("/"):
                if any(part == pattern[:-1] for part in rel_path.parts):
                    return True
            elif fnmatch.fnmatch(text, pattern) or fnmatch.fnmatch(
                rel_path.name, pattern
            ):
                return True
        return False

    def _is_ignored_dir(self, rel_dir: Path) -> bool:
        """Directory-level ignore (v1.17.7.1): patterns ending in `/` prune the
        walk so ignored subtrees are never descended into. Wildcards are
        supported (fnmatch) — `.venv*/` catches `.venv`, `.venv_sf3d`, ..."""
        for pattern in settings.ignore_patterns:
            if not pattern.endswith("/"):
                continue
            name = pattern[:-1]
            if any(fnmatch.fnmatch(part, name) for part in rel_dir.parts):
                return True
        return False

    def _is_skippable(self, rel_path: Path, absolute: Path) -> bool:
        """File-level gate (v1.17.7.1): ignore patterns, binary suffixes and
        the size cap. Shared by the full scan and incremental updates."""
        if self._is_ignored(rel_path):
            return True
        if absolute.suffix.lower() in _BINARY_SUFFIXES:
            return True
        try:
            return absolute.stat().st_size > settings.max_file_size_kb * 1024
        except OSError:
            return True

    def _iter_source_files(self, project_root: Path) -> list[Path]:
        """All parseable source files under the project root (sorted).

        v1.17.7.1: a depth-first walk that never descends into ignored
        directories (`.git`, `node_modules`, `.venv*`, `dist`, `data`, ...)
        — the previous `rglob` visited every file in those trees (24k entries
        in the Sentinel repo alone) and only filtered afterwards. Binary and
        oversized files are skipped without being read.
        """
        files: list[Path] = []
        stack: list[Path] = [project_root]
        while stack:
            base = stack.pop()
            try:
                with os.scandir(base) as entries:
                    names = list(entries)
            except OSError:
                continue
            for entry in names:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                if is_dir:
                    rel_dir = Path(entry.path).relative_to(project_root)
                    if not self._is_ignored_dir(rel_dir):
                        stack.append(Path(entry.path))
                    continue
                absolute = Path(entry.path)
                if self._is_skippable(absolute.relative_to(project_root), absolute):
                    continue
                files.append(absolute)
        return sorted(files, key=lambda p: p.relative_to(project_root).as_posix())

    def _index_files(self, project: Project) -> None:
        """Re-parse a project's tree without destroying row identity.

        v1.17.2: rows were previously deleted and re-inserted on every scan,
        which nulled every file's `embedding_id` — the knowledge index (and
        Chroma doc ids, which ARE the row ids) then re-embedded everything
        from scratch after each restart. Rows are now keyed by relative path:
        unchanged files keep their id + embedding_id, new files create rows,
        and only files gone from disk are removed.
        """
        project_root = Path(project.path)
        existing = {row.path: row for row in self.files.get_by_project(project.id)}
        seen: set[str] = set()
        for absolute in self._iter_source_files(project_root):
            rel = absolute.relative_to(project_root)
            seen.add(rel.as_posix())
            self._upsert_file(project, absolute, existing.get(rel.as_posix()))
        for path, row in existing.items():
            if path not in seen:
                self.session.delete(row)

    def _upsert_file(
        self,
        project: Project,
        absolute: Path,
        existing: ProjectFile | None = None,
    ) -> ProjectFile:
        rel = absolute.relative_to(Path(project.path))
        try:
            stat = absolute.stat()
        except OSError:
            return existing or ProjectFile(project_id=project.id, path=rel.as_posix())
        row = existing or self.files.get_by_path(project.id, rel.as_posix())
        # v1.17.7.1 fast path: an unchanged file (same size + mtime) is not
        # re-read or re-parsed — full scans stay cheap after the first pass.
        if (
            row is not None
            and row.mtime_ns == stat.st_mtime_ns
            and row.size_bytes == stat.st_size
        ):
            return row
        parsed = parse_file_for_project(absolute, project.language, project.framework)
        if row is None:
            row = ProjectFile(project_id=project.id, path=rel.as_posix())
        row.absolute_path = str(absolute)
        row.language = parsed.language if parsed else None
        row.size_bytes = stat.st_size
        row.mtime_ns = stat.st_mtime_ns
        self.session.add(row)
        return row

    def _index_dependencies(self, project: Project) -> None:
        self.dependencies.delete_by_project(project.id)
        for dep in self.extract_dependencies(project.path):
            dep.project_id = project.id
            self.session.add(dep)
