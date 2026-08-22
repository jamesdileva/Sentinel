"""Frozen backend entry point (Phase 2 packaging, v1.17.18.6).

Built by desktop/server/sentinel-server.spec into
desktop/resources/server-runtime/. Runs the full app in-process (a frozen
exe cannot re-spawn itself the way run.py does), so startup checks are
limited to what the lifespan doesn't already cover.

Data location contract (set by the Electron shell):
    SENTINEL_DB_PATH / SENTINEL_CHROMA_PATH / SENTINEL_WORLD_SIM_DB_PATH
point into the per-machine data dir (%LOCALAPPDATA%\\Sentinel\\data);
every other data path (screenshots, logs, backups) derives from db_path.
"""

import os

import uvicorn


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
