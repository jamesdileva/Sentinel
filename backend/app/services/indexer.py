"""IndexerService — orchestrates repository indexing.

Sprint 3 scope (docs/02 §3.1, docs/03 Sprint 3): deterministic language and
framework detection, file parsing, dependency extraction, and full/incremental
indexing into the knowledge database.
"""

import datetime
import fnmatch
import re
from pathlib import Path

from sqlmodel import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Dependency, Project, ProjectFile, ProjectStatus
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


def _pretty_name(directory_name: str) -> str:
    return directory_name.replace("-", " ").replace("_", " ").title()


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

    def scan_all_projects(self, watch_dirs: list[str] | None = None) -> list[Project]:
        """Discover known repositories (.git) under watch dirs and index them."""
        dirs = watch_dirs or settings.watch_dirs
        indexed: list[Project] = []
        for watch_dir in dirs:
            for repo_path in self.discover_repositories(watch_dir):
                try:
                    indexed.append(self.index_project(repo_path))
                except Exception:
                    logger.exception("Index failed for %s", repo_path)
        return indexed

    def discover_repositories(self, watch_dir: str | Path) -> list[Path]:
        """Find directories containing a `.git` folder, depth-limited."""
        root = Path(watch_dir)
        if not root.is_dir():
            return []
        if (root / ".git").exists():
            return [root]
        repos: list[Path] = []
        for entry in root.rglob("*"):
            rel = entry.relative_to(root)
            if len(rel.parts) > _DISCOVERY_DEPTH:
                continue
            if entry.is_dir() and (entry / ".git").exists():
                repos.append(entry)
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
                data = json.loads(package_json.read_text(encoding="utf-8"))
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
            if not absolute.exists() or self._is_ignored(
                absolute.relative_to(project_root)
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

    def _iter_source_files(self, project_root: Path) -> list[Path]:
        files: list[Path] = []
        for entry in project_root.rglob("*"):
            if entry.is_file() and not self._is_ignored(
                entry.relative_to(project_root)
            ):
                files.append(entry)
        return files

    def _index_files(self, project: Project) -> None:
        self.files.delete_by_project(project.id)
        project_root = Path(project.path)
        for absolute in self._iter_source_files(project_root):
            self._upsert_file(project, absolute)

    def _upsert_file(self, project: Project, absolute: Path) -> ProjectFile:
        rel = absolute.relative_to(Path(project.path))
        parsed = parse_file_for_project(absolute, project.language, project.framework)
        existing = self.files.get_by_path(project.id, rel.as_posix())
        row = existing or ProjectFile(project_id=project.id, path=rel.as_posix())
        row.absolute_path = str(absolute)
        row.language = parsed.language if parsed else None
        row.size_bytes = absolute.stat().st_size
        self.session.add(row)
        return row

    def _index_dependencies(self, project: Project) -> None:
        self.dependencies.delete_by_project(project.id)
        for dep in self.extract_dependencies(project.path):
            dep.project_id = project.id
            self.session.add(dep)
