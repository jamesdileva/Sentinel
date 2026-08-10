"""Application settings, loaded from environment variables (SENTINEL_*) and .env.

The .env file lives at the repo root (next to run.py); the docs, laptop.md,
and .env.example all agree. See docs/02_Implementation_Guide.md §4.2.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    version: str = "0.1.0"

    host: str = "127.0.0.1"
    port: int = 8000

    db_path: Path = BASE_DIR / "data" / "sqlite" / "sentinel.db"
    chroma_path: Path = BASE_DIR / "data" / "chroma"

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma2"
    embedding_model: str = "nomic-embed-text"
    ollama_timeout_seconds: int = 120

    # Defaults to the current user's home directory instead of a hardcoded
    # path, so a fresh install on any machine (e.g. the laptop, user `james`)
    # finds its repos with no SENTINEL_WATCH_DIRS setup.
    watch_dirs: list[str] = Field(default_factory=lambda: [str(Path.home())])
    ignore_patterns: list[str] = [
        ".git/",
        "__pycache__/",
        "node_modules/",
        ".venv/",
        "venv/",
        "dist/",
        "build/",
        "*.pyc",
        ".pytest_cache/",
    ]
    auto_scan_on_startup: bool = True
    auto_index_knowledge: bool = True  # queue RAG indexing for new/unembedded projects

    api_key: str = ""
    schedule_interval_minutes: int = 60

    scheduler_enabled: bool = True
    command_timeout_seconds: int = 300

    world_sim_enabled: bool = True
    world_sim_db_path: Path = BASE_DIR / "data" / "world_sim" / "world.db"
    world_sim_tick_seconds: int = 60
    world_sim_max_catchup_days: int = 48
    world_sim_time_scale: int = 1
    world_sim_seed: int = 42
    world_sim_starting_settlements: int = 2
    world_sim_model: str = "gemma2"
    world_sim_ai_narratives: bool = True

    max_recent_ollama_queries: int = 20

    # Repo auto-sync (Sprint 12.1): clone/pull projects from GitHub.
    github_token: str = ""  # read-only PAT; lists repos + optional private access
    sync_interval_minutes: int = 15


settings = Settings()
