"""RepoSyncService — deterministic GitHub clone/pull into watch dirs (Sprint 12.1).

Design (docs/01 Rule 3: determinism over generation) — syncing is a known,
reproducible workflow driven entirely by git, never by AI:

* The configured GitHub token lists the user's repos (GET /user/repos).
* For each repo, we look for a local `.git` checkout in this order:
  `<root>/<owner>/<repo>` (the canonical sync layout), then any checkout
  directly under the watch dir root whose origin remote URL matches
  `<owner>/<repo>` (v1.17.4: repos that pre-date the nested layout — e.g.
  `C:/Users/james/Projects/Sentinel` — are adopted and pulled, never
  cloned a second time). Missing repos are `git clone`d into the canonical
  location under the watch dir root (default: first SENTINEL_WATCH_DIRS).
* After the loop we re-index only the repos whose HEAD actually moved
  (Sprint 15 change detection): an unchanged pull results in zero scans —
  no re-parsing, no re-embedding, and no portfolio cache invalidation.
* Knowledge (RAG) indexing is queued only for projects under the changed
  repos that still have unembedded files (Sprint 12.2, narrowed in Sprint 15)
  — strictly best-effort: if Ollama or the broker is down we log and move on,
  never failing the sync for it.
* Every run is persisted to `SyncRun` (Sprint 15) so the dashboard pill and
  GET /api/v1/system/sync can show the last sync outcome.

Nothing mutates remote state; nothing is deleted. Big repo clones use the
longer `CLONE_TIMEOUT_SECONDS`, and git never prompts (GIT_TERMINAL_PROMPT=0).
Private repos clone only if git credentials are configured on the host (the
token lists them but is intentionally never embedded in remote URLs).
"""

import datetime
from pathlib import Path

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.core.logging import get_logger
from app.db.connection import get_engine
from app.db.models import SyncRun
from app.services.command_runner import git_command, run_command
from app.services.indexer import IndexerService
from app.services.ollama_service import OllamaService

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"
CLONE_TIMEOUT_SECONDS = 900  # a clone can legitimately take minutes


class RepoSyncService:
    """List GitHub repos and sync them into a local projects directory."""

    def __init__(
        self,
        token: str | None = None,
        root: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.token = token if token is not None else settings.github_token
        default_root = settings.watch_dirs[0] if settings.watch_dirs else "."
        self.root = root if root is not None else default_root
        self._client = httpx.Client(
            base_url=GITHUB_API,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            transport=transport,
            timeout=30,
        )

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def remote_repos(self) -> list[dict]:
        """Return [{full_name, clone_url}] for the token's repos.

        Pages through GET /user/repos (per_page=100) until it returns fewer
        than the page size; loop is bounded to 50 pages (5000 repos).
        v1.17.9.1: repos listed in SENTINEL_GITHUB_EXCLUDE are dropped before
        anything is cloned or pulled (case-insensitive full_name match).
        """
        excluded = {name.lower() for name in settings.github_exclude}
        repos: list[dict] = []
        for page in range(1, 51):
            response = self._client.get(
                "/user/repos", params={"per_page": 100, "page": page, "sort": "updated"}
            )
            response.raise_for_status()
            batch = response.json()
            for repo in batch:
                if repo["full_name"].lower() in excluded:
                    logger.info("Skipping excluded repo %s", repo["full_name"])
                    continue
                repos.append(
                    {
                        "full_name": repo["full_name"],
                        "url": repo["clone_url"],
                    }
                )
            if len(batch) < 100:
                break
        logger.info("Found %d remote repo(s) for token", len(repos))
        return repos

    def _local_path(self, full_name: str) -> str:
        owner, name = full_name.split("/", 1)
        expected = f"{self.root.rstrip('/')}/{owner}/{name}"
        if self._is_checkout(expected):
            return expected
        existing = self._find_existing_checkout(self.root, owner, name)
        return existing or expected

    @staticmethod
    def _find_existing_checkout(root: str, owner: str, name: str) -> str | None:
        """First checkout directly under `root` whose origin URL matches
        `owner/name` (v1.17.4). Adopts repos that predate the nested
        `<root>/<owner>/<repo>` layout instead of cloning duplicates;
        deterministic: matched only by git remote URL, never heuristics."""
        needle = f"{owner}/{name}".lower()
        root_path = Path(root)
        if not root_path.is_dir():
            return None
        for candidate in root_path.iterdir():
            git_dir = candidate / ".git"
            if not git_dir.is_dir():
                continue
            try:
                lines = (
                    (git_dir / "config")
                    .read_text(encoding="utf-8", errors="replace")
                    .splitlines()
                )
            except OSError:
                continue
            for line in lines:
                stripped = line.strip()
                if not stripped.startswith("url = "):
                    continue
                url = stripped.removeprefix("url = ").strip().lower()
                normalized = (
                    url.removesuffix(".git")
                    .replace("git@github.com:", "github.com/")
                    .replace("ssh://git@github.com/", "github.com/")
                    .removeprefix("https://")
                    .removeprefix("http://")
                )
                if normalized.endswith(needle):
                    return candidate.as_posix()
        return None

    def _sync_repo(self, repo: dict) -> str:
        local = self._local_path(repo["full_name"])
        env = {
            "GIT_TERMINAL_PROMPT": "0",
        }
        if self._is_checkout(local):
            result = run_command(
                f'"{git_command()}" pull --ff-only',
                cwd=local,
                timeout=CLONE_TIMEOUT_SECONDS,
                env=env,
            )
            if result.exit_code != 0:
                return f"pull failed: {result.stderr.strip()[:200]}"
            return "pulled"
        result = run_command(
            f'"{git_command()}" clone "{repo["url"]}" "{local}"',
            timeout=CLONE_TIMEOUT_SECONDS,
            env=env,
        )
        if result.exit_code != 0:
            return f"clone failed: {result.stderr.strip()[:200]}"
        return "cloned"

    @staticmethod
    def _is_checkout(local_path: str) -> bool:
        return Path(local_path).joinpath(".git").is_dir()

    def _head_sha(self, local: str) -> str | None:
        """Current HEAD of a checkout, or None when there is no checkout (or
        git cannot read it). Used to detect real changes after clone/pull."""
        if not self._is_checkout(local):
            return None
        result = run_command(
            f'"{git_command()}" rev-parse --short HEAD', cwd=local, timeout=60
        )
        if result.exit_code != 0:
            return None
        sha = result.stdout.strip()
        return sha or None

    def sync(self) -> dict:
        """Clone missing repos, pull existing ones, then re-index only the
        repos whose HEAD moved and queue knowledge for changed projects."""
        if not self.configured:
            raise ValueError("SENTINEL_GITHUB_TOKEN is not configured")
        # v1.17.3: fail fast with a visible message when git cannot be
        # resolved (Task Scheduler contexts have a minimal PATH) instead of
        # 18 individually failing clone/pull subprocesses.
        git_command()
        results = {"cloned": [], "pulled": [], "failed": {}}
        changed: list[str] = []
        for repo in self.remote_repos():
            local = self._local_path(repo["full_name"])
            before = self._head_sha(local)
            status = self._sync_repo(repo)
            if status == "cloned":
                results["cloned"].append(repo["full_name"])
                changed.append(repo["full_name"])
            elif status == "pulled":
                results["pulled"].append(repo["full_name"])
                if before != self._head_sha(local):
                    changed.append(repo["full_name"])
            else:
                results["failed"][repo["full_name"]] = status
        results["indexed"] = self._reindex(changed)
        results["knowledge"] = self._queue_knowledge_index(changed)
        results["ran_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        persist_sync_run(
            status="success",
            cloned=results["cloned"],
            pulled=results["pulled"],
            failed=results["failed"],
            indexed=results["indexed"],
            knowledge_queued=results["knowledge"].get("queued", 0),
        )
        return results

    def _reindex(self, changed: list[str]) -> int:
        """Index only repos whose HEAD actually moved (Sprint 15).

        When nothing changed the whole scan is skipped — no directory walks,
        no parsing, and portfolio caches stay valid.
        """
        if not changed:
            logger.info("No repo changes detected; skipping reindex")
            return 0
        dirs = [self._local_path(name) for name in changed]
        with Session(get_engine()) as session:
            return len(IndexerService(session).scan_all_projects(watch_dirs=dirs))

    def _queue_knowledge_index(self, changed: list[str]) -> dict:
        """Best-effort RAG indexing for projects under *changed* repos that
        still have unembedded files (Sprint 15: unchanged repos are skipped —
        their embeddings are already current).

        Never blocks or fails the sync: if Ollama is unreachable the projects
        are simply skipped (they can be indexed later via `sentinel rag-index`
        or the /rag/index API). Each queued project becomes one scheduler job.
        """
        if not changed:
            return {"queued": 0, "skipped": "no-changes"}
        return queue_knowledge_index_unembedded(
            [self._local_path(name) for name in changed]
        )


def queue_knowledge_index_unembedded(paths: list[str] | None = None) -> dict:
    """Best-effort RAG indexing for projects with unembedded files (v1.17).

    Shared by the repo-sync pass (path-filtered to changed repos) and the
    initial startup scan (no filter — every newly discovered project).
    Never raises: Ollama down or a DB hiccup degrades to {"queued": 0,
    "skipped": ...} and a later sync/scan retries it.
    """
    if paths is not None and not paths:
        return {"queued": 0, "skipped": "no-changes"}
    try:
        if not OllamaService().is_available():
            logger.info("Knowledge indexing skipped: Ollama unavailable")
            return {"queued": 0, "skipped": "ollama-unavailable"}
    except Exception:  # noqa: BLE001 — a probe failure means "not available"
        logger.info("Knowledge indexing skipped: Ollama probe failed")
        return {"queued": 0, "skipped": "ollama-unavailable"}

    try:
        from app.db.models import Project, ProjectFile
        from app.services.job_scheduler import scheduler as job_scheduler

        stmt = (
            select(ProjectFile.project_id)
            .join(Project, ProjectFile.project_id == Project.id)
            .where(ProjectFile.embedding_id.is_(None))
            .distinct()
        )
        if paths:
            stmt = stmt.where(Project.path.in_(paths))
        with Session(get_engine()) as session:
            unembedded = session.exec(stmt).all()
        for project_id in unembedded:
            try:
                # with_summary=True (v1.17.6.2): auto-indexing always includes
                # the AI architecture summary; ingest_project_summary dedupes
                # to once per project.
                job_scheduler.submit("run_index_knowledge", args=[project_id, True])
            except Exception:  # noqa: BLE001 — one bad queue must not kill the run
                logger.warning("Knowledge queuing failed for %s", project_id)
        return {"queued": len(unembedded), "skipped": None}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Knowledge indexing step failed: %s", exc)
        return {"queued": 0, "skipped": f"error: {exc}"}


def persist_sync_run(
    status: str,
    cloned: list[str] | None = None,
    pulled: list[str] | None = None,
    failed: dict | None = None,
    indexed: int = 0,
    knowledge_queued: int = 0,
    detail: str | None = None,
) -> None:
    """Record a sync run in `SyncRun` for /system/sync. Best-effort: a DB
    problem is logged, never raised — the sync outcome has already happened."""
    try:
        with Session(get_engine()) as session:
            session.add(
                SyncRun(
                    status=status,
                    cloned=cloned or [],
                    pulled=pulled or [],
                    failed=failed or {},
                    indexed=indexed,
                    knowledge_queued=knowledge_queued,
                    detail=detail,
                )
            )
            session.commit()
    except Exception:  # noqa: BLE001 — persistence must never break the run
        logger.exception("Failed to persist sync run status")


def latest_sync_run(session: Session) -> dict | None:
    """Most recent syncRun, or None when no sync has ever run successfully."""
    stmt = select(SyncRun).order_by(SyncRun.ran_at.desc())
    row = session.exec(stmt).first()
    if row is None:
        return None
    ran_at = row.ran_at
    if ran_at is not None and ran_at.tzinfo is None:  # stored naive UTC
        ran_at = ran_at.replace(tzinfo=datetime.timezone.utc)
    return {
        "status": row.status,
        "ran_at": ran_at.isoformat() if ran_at else None,
        "cloned": row.cloned,
        "pulled": row.pulled,
        "failed": row.failed,
        "indexed": row.indexed,
        "knowledge_queued": row.knowledge_queued,
        "detail": row.detail,
    }


def run_sync(service: RepoSyncService | None = None) -> dict:
    """Entry point used by both the CLI and the Celery beat task."""
    service = service or RepoSyncService()
    if not service.configured:
        logger.warning("GitHub sync skipped: SENTINEL_GITHUB_TOKEN not configured")
        persist_sync_run(status="skipped", detail="token not configured")
        return {"configured": False, "skipped": True}
    try:
        return service.sync()
    except httpx.HTTPError as exc:
        logger.error("GitHub sync failed: %s", exc)
        persist_sync_run(status="error", detail=f"{exc.__class__.__name__}: {exc}")
        return {"configured": True, "error": f"{exc.__class__.__name__}: {exc}"}
    except FileNotFoundError as exc:
        # v1.17.3: git unavailable (minimal-PATH contexts) — say exactly that.
        logger.error("GitHub sync failed: %s", exc)
        persist_sync_run(status="error", detail=str(exc))
        return {"configured": True, "error": str(exc)}
