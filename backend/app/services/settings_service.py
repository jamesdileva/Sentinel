"""SettingsService — read-only configuration report (v1.17.18.1).

Surfaces every SENTINEL_* setting with its current value, default and source
(environment / .env file / default), plus deterministic validation warnings
(watch-dir existence, port sanity, DB/chroma path writability, Ollama
reachability, embedding-model presence). Strictly read-only (docs/01 Rule 2:
nothing here changes server state); the dashboard renders the report and
provides no edit controls.

Secrets (`SENTINEL_GITHUB_TOKEN`) are redacted to set/not-set — the values
never leave the machine (docs/01 Rule 1). v1.17.18.1: removed dead
`SENTINEL_API_KEY` (no consumer — audit A5).
"""

import datetime
import os
from pathlib import Path

from app.core.config import BASE_DIR, Settings, settings
from app.core.logging import get_logger
from app.services.ollama_service import OllamaService
from app.services.startup_check import _check_chroma, _check_watch_dirs

logger = get_logger(__name__)

# Setting catalog: key (env name) → display label, group, and the Settings
# field name on the pydantic model. Value/default come from the model; only
# the label/group mapping is declared here (Rule 4: one responsibility).
CATALOG: list[dict] = [
    {
        "key": "SENTINEL_APP_NAME",
        "label": "App name",
        "group": "Server",
        "field": "app_name",
    },
    # v1.17.18.4 (audit2 C11): SENTINEL_HOST removed — dead setting; run.py
    # always binds 127.0.0.1 (Rule 1).
    {"key": "SENTINEL_PORT", "label": "Port", "group": "Server", "field": "port"},
    {
        "key": "SENTINEL_VERSION",
        "label": "Version",
        "group": "Server",
        "field": "version",
    },
    {
        "key": "SENTINEL_DB_PATH",
        "label": "SQLite database",
        "group": "Paths",
        "field": "db_path",
    },
    {
        "key": "SENTINEL_CHROMA_PATH",
        "label": "ChromaDB dir",
        "group": "Paths",
        "field": "chroma_path",
    },
    {
        "key": "SENTINEL_WATCH_DIRS",
        "label": "Watch dirs",
        "group": "Paths",
        "field": "watch_dirs",
    },
    {
        "key": "SENTINEL_PORTFOLIO_DIR",
        "label": "Portfolio export dir",
        "group": "Paths",
        "field": "portfolio_dir",
    },
    {
        "key": "SENTINEL_OLLAMA_HOST",
        "label": "Ollama host",
        "group": "AI",
        "field": "ollama_host",
    },
    {
        "key": "SENTINEL_OLLAMA_MODEL",
        "label": "Generation model",
        "group": "AI",
        "field": "ollama_model",
    },
    {
        "key": "SENTINEL_EMBEDDING_MODEL",
        "label": "Embedding model",
        "group": "AI",
        "field": "embedding_model",
    },
    {
        "key": "SENTINEL_OLLAMA_TIMEOUT_SECONDS",
        "label": "Ollama timeout (s)",
        "group": "AI",
        "field": "ollama_timeout_seconds",
    },
    {
        "key": "SENTINEL_OLLAMA_NUM_CTX",
        "label": "Ollama context (num_ctx)",
        "group": "AI",
        "field": "ollama_num_ctx",
    },
    {
        "key": "SENTINEL_OLLAMA_SUMMARY_MAX_TOKENS",
        "label": "Summary max tokens",
        "group": "AI",
        "field": "ollama_summary_max_tokens",
    },
    {
        "key": "SENTINEL_MAX_RECENT_OLLAMA_QUERIES",
        "label": "Recent queries kept",
        "group": "AI",
        "field": "max_recent_ollama_queries",
    },
    {
        "key": "SENTINEL_IGNORE_PATTERNS",
        "label": "Ignore patterns",
        "group": "Ops",
        "field": "ignore_patterns",
    },
    {
        "key": "SENTINEL_MAX_FILE_SIZE_KB",
        "label": "Max file size (KB)",
        "group": "Ops",
        "field": "max_file_size_kb",
    },
    {
        "key": "SENTINEL_AUTO_SCAN_ON_STARTUP",
        "label": "Scan on startup",
        "group": "Ops",
        "field": "auto_scan_on_startup",
    },
    {
        "key": "SENTINEL_AUTO_INDEX_KNOWLEDGE",
        "label": "Auto knowledge index",
        "group": "Ops",
        "field": "auto_index_knowledge",
    },
    {
        "key": "SENTINEL_SCHEDULER_ENABLED",
        "label": "Scheduler",
        "group": "Ops",
        "field": "scheduler_enabled",
    },
    {
        "key": "SENTINEL_COMMAND_TIMEOUT_SECONDS",
        "label": "Command timeout (s)",
        "group": "Ops",
        "field": "command_timeout_seconds",
    },
    {
        "key": "SENTINEL_GITHUB_TOKEN",
        "label": "GitHub token",
        "group": "Ops",
        "field": "github_token",
        "secret": True,
    },
    {
        "key": "SENTINEL_GITHUB_EXCLUDE",
        "label": "GitHub excluded repos",
        "group": "Ops",
        "field": "github_exclude",
    },
    {
        "key": "SENTINEL_SYNC_INTERVAL_MINUTES",
        "label": "Repo-sync interval (min)",
        "group": "Ops",
        "field": "sync_interval_minutes",
    },
    {
        "key": "SENTINEL_SCAN_INTERVAL_MINUTES",
        "label": "Security scan interval (min)",
        "group": "Ops",
        "field": "scan_interval_minutes",
    },
    {
        "key": "SENTINEL_GIT_EXECUTABLE",
        "label": "Git executable",
        "group": "Ops",
        "field": "git_executable",
    },
    {
        "key": "SENTINEL_WORLD_SIM_ENABLED",
        "label": "World simulator",
        "group": "World Sim",
        "field": "world_sim_enabled",
    },
    {
        "key": "SENTINEL_WORLD_SIM_DB_PATH",
        "label": "World sim database",
        "group": "World Sim",
        "field": "world_sim_db_path",
    },
    {
        "key": "SENTINEL_WORLD_SIM_TICK_SECONDS",
        "label": "World sim tick (s)",
        "group": "World Sim",
        "field": "world_sim_tick_seconds",
    },
    {
        "key": "SENTINEL_WORLD_SIM_MAX_CATCHUP_DAYS",
        "label": "World sim max catch-up (d)",
        "group": "World Sim",
        "field": "world_sim_max_catchup_days",
    },
    {
        "key": "SENTINEL_WORLD_SIM_TIME_SCALE",
        "label": "World sim time scale",
        "group": "World Sim",
        "field": "world_sim_time_scale",
    },
    {
        "key": "SENTINEL_WORLD_SIM_SEED",
        "label": "World sim seed",
        "group": "World Sim",
        "field": "world_sim_seed",
    },
    {
        "key": "SENTINEL_WORLD_SIM_STARTING_SETTLEMENTS",
        "label": "World sim starting settlements",
        "group": "World Sim",
        "field": "world_sim_starting_settlements",
    },
    {
        "key": "SENTINEL_WORLD_SIM_MODEL",
        "label": "World sim model",
        "group": "World Sim",
        "field": "world_sim_model",
    },
    {
        "key": "SENTINEL_WORLD_SIM_AI_NARRATIVES",
        "label": "World sim AI narratives",
        "group": "World Sim",
        "field": "world_sim_ai_narratives",
    },
]


def _env_sources() -> set[str]:
    """Names of SENTINEL_* vars set in the environment or the .env file."""
    keys = {k for k in os.environ if k.startswith("SENTINEL_")}
    env_file = BASE_DIR / ".env"
    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    name = stripped.split("=", 1)[0].strip()
                    if name.startswith("SENTINEL_"):
                        keys.add(name)
        except OSError:
            logger.warning("Could not read %s", env_file)
    return keys


def _format_value(field_name: str, value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "(empty)"
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _default_for(field_name: str) -> object:
    info = Settings.model_fields.get(field_name)
    if info is None:
        return None
    if info.default is not None:
        return info.default
    if info.default_factory is not None:
        try:
            return info.default_factory()
        except Exception:  # noqa: BLE001  defensive
            return None
    return None


def _validation_warnings() -> list[dict]:
    """Deterministic config warnings. Reuses startup-check logic where it
    exists; never raises (a config probe must not break the page)."""
    warnings: list[dict] = []

    watch = _check_watch_dirs()
    if not watch.ok:
        warnings.append(
            {"key": "watch_dirs", "level": "error", "message": watch.detail}
        )

    chroma = _check_chroma(settings.chroma_path)
    if not chroma.ok:
        warnings.append(
            {"key": "chroma_path", "level": "error", "message": chroma.detail}
        )

    if not (1 <= settings.port <= 65535):
        warnings.append(
            {
                "key": "port",
                "level": "error",
                "message": f"Port {settings.port} is out of range 1-65535",
            }
        )

    db_parent = settings.db_path.parent
    if not db_parent.exists() or not os.access(str(db_parent), os.W_OK):
        warnings.append(
            {
                "key": "db_path",
                "level": "warning",
                "message": f"SQLite directory is not writable: {db_parent}",
            }
        )

    try:
        ollama = OllamaService(timeout_seconds=2)  # short probe, not the 1800s default
        try:
            available = ollama.is_available()
            models: list[str] = []
            if available:
                models = ollama.list_models()
        finally:
            ollama.close()  # v1.17.18.3 (audit2 S1): probe runs per page load
        if not available:
            warnings.append(
                {
                    "key": "ollama",
                    "level": "warning",
                    "message": f"Ollama unreachable at {settings.ollama_host}",
                }
            )
        else:
            # /api/tags returns names with the `:latest` suffix; the config
            # name without it resolves to the same model (Ollama default tag).
            installed = {
                m.split(":", 1)[0] if m.endswith(":latest") else m for m in models
            }
            if settings.embedding_model not in installed:
                warnings.append(
                    {
                        "key": "embedding_model",
                        "level": "warning",
                        "message": f"Embedding model {settings.embedding_model} is not installed",
                    }
                )
    except Exception:  # noqa: BLE001  probe only
        warnings.append(
            {
                "key": "ollama",
                "level": "warning",
                "message": f"Ollama probe failed at {settings.ollama_host}",
            }
        )

    return warnings


def settings_report() -> dict:
    """Full read-only settings report for GET /api/v1/settings."""
    sources = _env_sources()
    groups: dict[str, list[dict]] = {}
    for entry in CATALOG:
        field = entry["field"]
        value = getattr(settings, field, None)
        if entry.get("secret"):
            display = "set" if value else "not set"
            value_display = display
            default_display = "set" if _default_for(field) else "not set"
        else:
            value_display = _format_value(field, value)
            default_display = _format_value(field, _default_for(field))
        source = "env" if entry["key"] in sources else "default"
        groups.setdefault(entry["group"], []).append(
            {
                "key": entry["key"],
                "label": entry["label"],
                "value": value_display,
                "default": default_display,
                "source": source,
                "secret": bool(entry.get("secret")),
            }
        )

    ordered = ["Server", "Paths", "AI", "Ops", "World Sim"]
    group_list = [
        {"name": name, "items": groups[name]} for name in ordered if name in groups
    ]

    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version": settings.version,
        "groups": group_list,
        "warnings": _validation_warnings(),
    }
