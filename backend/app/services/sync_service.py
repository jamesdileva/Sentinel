"""RepoSyncService — deterministic GitHub clone/pull into watch dirs (Sprint 12.1).

Design (docs/01 Rule 3: determinism over generation) — syncing is a known,
reproducible workflow driven entirely by git, never by AI:

* The configured GitHub token lists the user's repos (GET /user/repos).
* For each repo, if the local directory already holds a `.git` checkout we
  `git pull --ff-only`; otherwise we `git clone` it directly under the
  configured watch dir root (default: first entry of SENTINEL_WATCH_DIRS).
* After the loop we re-run the indexer so new projects become known.

Nothing mutates remote state; nothing is deleted. Big repo clones use the
longer `CLONE_TIMEOUT_SECONDS`, and git never prompts (GIT_TERMINAL_PROMPT=0).
Private repos clone only if git credentials are configured on the host (the
token lists them but is intentionally never embedded in remote URLs).
"""

import datetime
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.command_runner import run_command
from app.services.indexer import IndexerService

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
        """
        repos: list[dict] = []
        for page in range(1, 51):
            response = self._client.get(
                "/user/repos", params={"per_page": 100, "page": page, "sort": "updated"}
            )
            response.raise_for_status()
            batch = response.json()
            repos.extend(
                {
                    "full_name": repo["full_name"],
                    "url": repo["clone_url"],
                }
                for repo in batch
            )
            if len(batch) < 100:
                break
        logger.info("Found %d remote repo(s) for token", len(repos))
        return repos

    def _local_path(self, full_name: str) -> str:
        owner, name = full_name.split("/", 1)
        return f"{self.root.rstrip('/')}/{owner}/{name}"

    def _sync_repo(self, repo: dict) -> str:
        local = self._local_path(repo["full_name"])
        env = {
            "GIT_TERMINAL_PROMPT": "0",
        }
        if self._is_checkout(local):
            result = run_command(
                "git pull --ff-only", cwd=local, timeout=CLONE_TIMEOUT_SECONDS, env=env
            )
            if result.exit_code != 0:
                return f"pull failed: {result.stderr.strip()[:200]}"
            return "pulled"
        result = run_command(
            f"git clone '{repo['url']}' '{local}'",
            timeout=CLONE_TIMEOUT_SECONDS,
            env=env,
        )
        if result.exit_code != 0:
            return f"clone failed: {result.stderr.strip()[:200]}"
        return "cloned"

    @staticmethod
    def _is_checkout(local_path: str) -> bool:
        return Path(local_path).joinpath(".git").is_dir()

    def sync(self) -> dict:
        """Clone missing repos, pull existing ones, then re-index over them."""
        if not self.configured:
            raise ValueError("SENTINEL_GITHUB_TOKEN is not configured")
        results = {"cloned": [], "pulled": [], "failed": {}}
        for repo in self.remote_repos():
            status = self._sync_repo(repo)
            if status == "cloned":
                results["cloned"].append(repo["full_name"])
            elif status == "pulled":
                results["pulled"].append(repo["full_name"])
            else:
                results["failed"][repo["full_name"]] = status
        results["indexed"] = self._reindex()
        results["ran_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return results

    def _reindex(self) -> int:
        from sqlmodel import Session

        from app.db.connection import get_engine

        with Session(get_engine()) as session:
            projects = IndexerService(session).scan_all_projects(watch_dirs=[self.root])
        return len(projects)


def run_sync(service: RepoSyncService | None = None) -> dict:
    """Entry point used by both the CLI and the Celery beat task."""
    service = service or RepoSyncService()
    if not service.configured:
        logger.warning("GitHub sync skipped: SENTINEL_GITHUB_TOKEN not configured")
        return {"configured": False, "skipped": True}
    try:
        return service.sync()
    except httpx.HTTPError as exc:
        logger.error("GitHub sync failed: %s", exc)
        return {"configured": True, "error": f"{exc.__class__.__name__}: {exc}"}
