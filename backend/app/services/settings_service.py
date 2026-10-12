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
import time
from pathlib import Path

from app.core.config import BASE_DIR, Settings, is_loopback_host, settings
from app.core.logging import get_logger
from app.services.ollama_service import OllamaService
from app.services.startup_check import _check_chroma, _check_watch_dirs

logger = get_logger(__name__)

# v1.17.19.21 (audit B9): provenance is stated exactly as the UI promises it.
# A value found in the process environment and one found in `.env` used to
# both report "env", which hid the difference the Settings page shows:
# process env wins over `.env` at load, so they are not interchangeable.
SOURCE_ENV = "env"
SOURCE_ENV_FILE = "env-file"
SOURCE_DEFAULT = "default"

# v1.17.19.21 (audit Batch 4): the Ollama probe used to run on every Settings
# page load — a live request against a local service for a report that cannot
# have changed in seconds. Cached for a short TTL: long enough that opening the
# page twice costs nothing, short enough that "restart Ollama, reload the page"
# still tells the truth.
_PROBE_TTL_SECONDS = 30.0
_probe_cache: dict[str, object] = {"key": None, "at": 0.0, "result": None}

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
        "key": "SENTINEL_ALLOW_REMOTE_OLLAMA",
        "label": "Allow remote Ollama host",
        "group": "AI",
        "field": "allow_remote_ollama",
    },
    {
        "key": "SENTINEL_OLLAMA_MODEL",
        "label": "Generation model",
        "group": "AI",
        "field": "ollama_model",
    },
    {
        "key": "SENTINEL_OLLAMA_SUMMARY_MODEL",
        "label": "Summary model",
        "group": "AI",
        "field": "ollama_summary_model",
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
        "key": "SENTINEL_OLLAMA_KEEP_ALIVE",
        "label": "Ollama keep alive",
        "group": "AI",
        "field": "ollama_keep_alive",
    },
    {
        "key": "SENTINEL_OLLAMA_DYNAMIC_CTX",
        "label": "Dynamic context sizing",
        "group": "AI",
        "field": "ollama_dynamic_ctx",
    },
    {
        "key": "SENTINEL_OLLAMA_SUMMARY_MAX_TOKENS",
        "label": "Summary max tokens",
        "group": "AI",
        "field": "ollama_summary_max_tokens",
    },
    {
        "key": "SENTINEL_RAG_RELEVANCE_FLOOR",
        "label": "RAG relevance floor (cosine distance)",
        "group": "AI",
        "field": "rag_relevance_floor",
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


def _dotenv_keys() -> set[str]:
    """Names set in the repo's `.env` file (parsed, not evaluated)."""
    keys: set[str] = set()
    env_file = BASE_DIR / ".env"
    if not env_file.is_file():
        return keys
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        logger.warning("Could not read %s", env_file)
        return keys
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        if name.startswith("SENTINEL_"):
            keys.add(name)
    return keys


def _source_for(key: str, process_env: set[str], dotenv: set[str]) -> str:
    """Exact provenance (audit B9). Process environment wins over `.env`, which
    is pydantic-settings' own load order, so the label matches the behaviour."""
    if key in process_env:
        return SOURCE_ENV
    if key in dotenv:
        return SOURCE_ENV_FILE
    return SOURCE_DEFAULT


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


def _probe_ollama() -> tuple[bool, list[str]]:
    """Reachable + installed models, cached for `_PROBE_TTL_SECONDS`.

    The cache is keyed on what is being probed (the probing class, the host
    and the models) — never just the answer. Changing `SENTINEL_OLLAMA_HOST`
    (or swapping the probe for a fake) is picked up immediately rather than
    serving the previous configuration's answer.
    """
    global _probe_cache
    key = (
        OllamaService,
        settings.ollama_host,
        settings.embedding_model,
        settings.ollama_summary_model,
    )
    now = time.monotonic()
    cached = _probe_cache.get("result")
    if (
        _probe_cache.get("key") == key
        and now - float(_probe_cache.get("at") or 0) < _PROBE_TTL_SECONDS
    ):
        return cached  # type: ignore[return-value]

    try:
        ollama = OllamaService(timeout_seconds=2)  # short probe, not the 1800s default
        try:
            available = ollama.is_available()
            models = ollama.list_models() if available else []
        finally:
            ollama.close()  # v1.17.18.3 (audit2 S1): probe runs per page load
        result = (available, models)
    except Exception:  # noqa: BLE001 — a probe failure is a result, not a crash
        result = (False, [])
    _probe_cache = {"key": key, "at": now, "result": result}
    return result


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

    # v1.17.19.15 (audit A5): Rule 1 made visible. The RAG path sends source
    # code, docs, summaries and user questions to this host, so a non-loopback
    # host without the explicit opt-in is an error-level warning — it is the
    # one setting that can silently turn Sentinel into an exfiltration path.
    if (
        settings.ollama_host
        and not is_loopback_host(settings.ollama_host)
        and not settings.allow_remote_ollama
    ):
        warnings.append(
            {
                "key": "ollama_host",
                "level": "error",
                "message": (
                    f"{settings.ollama_host} is not loopback, so Sentinel refuses "
                    "to send project data to it (Rule 1: everything stays local). "
                    "Set SENTINEL_ALLOW_REMOTE_OLLAMA=true to allow it deliberately."
                ),
            }
        )

    available, models = _probe_ollama()
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
        installed = {m.split(":", 1)[0] if m.endswith(":latest") else m for m in models}
        if settings.embedding_model not in installed:
            warnings.append(
                {
                    "key": "embedding_model",
                    "level": "warning",
                    "message": f"Embedding model {settings.embedding_model} is not installed",
                }
            )
        # v1.17.19.6: the summary model is a second, independent model —
        # warn separately so a missing qwen3.5:9b doesn't masquerade as
        # "Ollama is fine".
        if (
            settings.ollama_summary_model != settings.ollama_model
            and settings.ollama_summary_model not in installed
        ):
            warnings.append(
                {
                    "key": "ollama_summary_model",
                    "level": "warning",
                    "message": (
                        f"Summary model {settings.ollama_summary_model} is not "
                        "installed — architecture summaries will fall back to "
                        "an error until `ollama pull` or a config change."
                    ),
                }
            )

    return warnings


def settings_report() -> dict:
    """Full read-only settings report for GET /api/v1/settings."""
    process_env = {k for k in os.environ if k.startswith("SENTINEL_")}
    dotenv = _dotenv_keys()
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
        source = _source_for(entry["key"], process_env, dotenv)
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
