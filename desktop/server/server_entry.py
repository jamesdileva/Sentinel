"""Frozen backend entry point (Phase 2 packaging, v1.17.18.6).

Built by desktop/server/sentinel-server.spec into
desktop/resources/server-runtime/. Runs the full app in-process (a frozen
exe cannot re-spawn itself the way run.py does), so startup checks are
limited to what the lifespan doesn't already cover.

Data location contract (set by the Electron shell):
    SENTINEL_DB_PATH / SENTINEL_CHROMA_PATH / SENTINEL_WORLD_SIM_DB_PATH
point either at the checkout's data/ (when the shell found a dataset there)
or at the per-machine data dir (%LOCALAPPDATA%\\Sentinel\\data);
every other data path (screenshots, logs, backups) derives from db_path.
SENTINEL_REPO_ROOT additionally lets a frozen server honor the checkout's
.env (watch dirs, token, Ollama host) — explicit shell vars always win.
"""

import os
import sys

import uvicorn


def _load_repo_env() -> None:
    """Load the checkout's .env for a frozen server running beside one.

    The bundle never sees the repo .env (pydantic reads <bundle>/.env,
    which doesn't exist), so watch dirs / token / Ollama host silently
    reverted to defaults. With override=False, anything the shell set
    explicitly (DB paths, port) keeps winning.
    """
    if not getattr(sys, "frozen", False):
        return
    root = os.environ.get("SENTINEL_REPO_ROOT")
    if not root:
        return
    dotenv_path = os.path.join(root, ".env")
    if not os.path.isfile(dotenv_path):
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path, override=False)
    except Exception:  # noqa: BLE001 — .env is convenience, never fatal
        pass


def main() -> None:
    host = "127.0.0.1"  # Rule 1: loopback only, never LAN-exposed
    port = int(os.environ.get("SENTINEL_PORT", "8420"))

    # Ensure relocated data dirs exist before anything opens a handle.
    for key in (
        "SENTINEL_DB_PATH",
        "SENTINEL_CHROMA_PATH",
        "SENTINEL_WORLD_SIM_DB_PATH",
    ):
        raw = os.environ.get(key)
        if raw:
            parent = os.path.dirname(raw)
            if parent:
                os.makedirs(parent, exist_ok=True)

    # Imports stay here (not module level) so PyInstaller bundles them after
    # the runtime hooks above have run; static/prompts resolve via _MEIPASS.
    _load_repo_env()
    from app.main import app

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
