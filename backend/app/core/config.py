"""Application settings, loaded from environment variables (SENTINEL_*) and .env.

The .env file lives at the repo root (next to run.py); the docs, laptop.md,
and .env.example all agree. See docs/02_Implementation_Guide.md §4.2.
"""

import json
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app import __version__

# Repo root: sentinel/ (data lives at repo root, see docs/01 §13)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Project Sentinel"
    # Single source of truth: app/__init__.py (CLI --version, health, release).
    version: str = __version__

    host: str = "127.0.0.1"
    # v1.17.8.1: 8420, not 8000 — the dev servers of indexed projects (Cg,
    # Demake Engine) default to uvicorn's 8000, so build→open can bind it.
    port: int = 8420

    db_path: Path = BASE_DIR / "data" / "sqlite" / "sentinel.db"
    chroma_path: Path = BASE_DIR / "data" / "chroma"

    ollama_host: str = "http://localhost:11434"
    # v1.17.6.5: llama3.1:8b won the head-to-head over gemma2 on the
    # architecture-summary prompt (better structure, ~40% faster tok/s,
    # stronger instruction following); see docs changelog for the test.
    ollama_model: str = "llama3.1:8b"
    embedding_model: str = "nomic-embed-text"
    ollama_timeout_seconds: int = 1800  # v1.17.6.4: 120s timed out arch-summary
    # generation while embedding workers were saturating the local Ollama
    # v1.17.6.8: 600s still timed out with the v1.17.6.6 doc-first summary
    # context (~10k-token prefill) contending with a full re-index; 1800s
    # covers the slowest laptop generation.
    # v1.17.6.6: llama3.1:8b supports 128k context, but Ollama's default
    # num_ctx is only 2048 — big summary/query prompts would be silently
    # truncated. 32768 covers the largest prompt we build (~12k tokens) with
    # room to spare and a modest KV-cache memory footprint on the laptop.
    ollama_num_ctx: int = 32768
    # v1.17.6.8: summaries get more output budget than the shared 500-token
    # default (chat answers stay concise) — the doc-first prompt feeds ~10k
    # tokens of context, and a structured components/stack/notes summary
    # grows past 500. 1250 tokens ~= 2-2.5 min on the laptop, inside the
    # 1800s timeout.
    ollama_summary_max_tokens: int = 1250

    # Defaults to the current user's home directory instead of a hardcoded
    # path, so a fresh install on any machine (e.g. the laptop, user `james`)
    # finds its repos with no SENTINEL_WATCH_DIRS setup.
    # v1.17.7.3: NoDecode + before-validator — the docs always promised
    # comma-separated values, but pydantic-settings' complex-field parser
    # only accepted JSON and raised SettingsError on the documented format.
    # Plain, comma-separated and JSON forms are all accepted now.
    watch_dirs: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [str(Path.home())]
    )

    @field_validator("watch_dirs", mode="before")
    @classmethod
    def _parse_watch_dirs(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON for SENTINEL_WATCH_DIRS: {value!r}"
                ) from exc
        return [part.strip() for part in text.split(",") if part.strip()]

    # v1.17.7.1: `data/` — a repo's own database/chroma/logs must never be
    # parsed as project files; `.venv*/` (wildcard dir pattern) covers odd
    # venv names like `.venv_sf3d` that the exact `.venv/` missed.
    # v1.17.7.2: `Library/` (Unity's regenerable cache — PackageCache,
    # Artifacts, BurstCache), `release/` + `win-unpacked/` (electron-builder
    # output) and `*.pdb`/`*.bhc` (build symbols / Unity Burst caches) —
    # build artifacts bloat the file index (47k files vs ~4k real source).
    ignore_patterns: list[str] = [
        ".git/",
        "__pycache__/",
        "node_modules/",
        ".venv*/",
        "venv/",
        "dist/",
        "build/",
        "data/",
        "Library/",
        "release/",
        "win-unpacked/",
        "*.pyc",
        "*.pdb",
        "*.bhc",
        ".pytest_cache/",
    ]
    # v1.17.7.1: files larger than this are never parsed or stored as project
    # files. ML models (multi-GB ONNX/checkpoints), media and other binaries
    # bloated the file walk and were read fully by the parsers.
    max_file_size_kb: int = 5120
    auto_scan_on_startup: bool = True
    auto_index_knowledge: bool = True  # queue RAG indexing for new/unembedded projects

    api_key: str = ""

    scheduler_enabled: bool = True
    command_timeout_seconds: int = 300

    # v1.17.7.3: off by default — the world simulator is an opt-in toy; the
    # API router and the beat tick register only when it is enabled.
    world_sim_enabled: bool = False
    world_sim_db_path: Path = BASE_DIR / "data" / "world_sim" / "world.db"
    world_sim_tick_seconds: int = 60
    world_sim_max_catchup_days: int = 48
    world_sim_time_scale: int = 1
    world_sim_seed: int = 42
    world_sim_starting_settlements: int = 2
    world_sim_model: str = "llama3.1:8b"  # unused today (narratives are deterministic)
    world_sim_ai_narratives: bool = True

    max_recent_ollama_queries: int = 20

    # Repo auto-sync (Sprint 12.1): clone/pull projects from GitHub.
    github_token: str = ""  # read-only PAT; lists repos + optional private access
    # v1.17.1: daily cadence — startup always syncs once, then every 24h unless
    # the user presses the header "Sync now" button (POST /api/v1/system/sync).
    sync_interval_minutes: int = 1440
    # v1.17.7: the daily security scan-all runs on its own beat instead of
    # riding the repo-sync pass — a tokenless install (all projects already
    # local) still scans on schedule.
    scan_interval_minutes: int = 1440
    # v1.17.3: full path to a git executable, for contexts with a minimal PATH
    # (Task Scheduler autostart). Auto-discovered when empty.
    git_executable: str = ""


settings = Settings()
