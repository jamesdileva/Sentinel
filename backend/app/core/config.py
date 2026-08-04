"""Application settings, loaded from environment variables (SENTINEL_*) and .env.

See docs/02_Implementation_Guide.md §4.2 for the full variable reference.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: sentinel/ (data lives at repo root, see docs/01 §13)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=BASE_DIR.parent / ".env",
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

    watch_dirs: list[str] = ["C:\\Users\\j"]
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

    api_key: str = ""
    schedule_interval_minutes: int = 60


settings = Settings()
