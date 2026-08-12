"""Logging setup for the Sentinel backend.

Every run writes a per-run log to `data/logs/sentinel.log` (v1.17.6.3): it is
truncated when the run starts and captures everything at INFO level — "what
happened this run". The file handler is attached to the root logger and to
uvicorn's own loggers; `attach_file_logging()` re-attaches it at app startup
because uvicorn's log config replaces the root handlers after the app module
is imported.
"""

import logging
import sys
from pathlib import Path

from app.core.config import settings

_FORMATTER = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

_FILE_HANDLER: logging.Handler | None = None
_CONSOLE_HANDLER: logging.Handler | None = None
_CONFIGURED = False


def run_log_path() -> Path:
    return settings.chroma_path.parent / "logs" / "sentinel.log"


def _make_console_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_FORMATTER)
    return handler


def _make_file_handler() -> logging.Handler:
    path = run_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(_FORMATTER)
    return handler


def _quiet_http_client_loggers() -> None:
    """httpx logs every HTTP request at INFO (the v1.17.6.3 run log was ~500
    `POST /api/embed` lines in 1800); the request detail lives in the
    activity feed and Ollama query log instead."""
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def setup_logging(level: int = logging.INFO) -> None:
    """Idempotent: console handler + per-run file handler on the root logger."""
    global _CONFIGURED, _CONSOLE_HANDLER, _FILE_HANDLER
    if _CONFIGURED:
        return
    _quiet_http_client_loggers()
    root = logging.getLogger()
    root.setLevel(level)
    if _CONSOLE_HANDLER is None:
        _CONSOLE_HANDLER = _make_console_handler()
        root.addHandler(_CONSOLE_HANDLER)
    if _FILE_HANDLER is None:
        _FILE_HANDLER = _make_file_handler()
    root.addHandler(_FILE_HANDLER)
    _CONFIGURED = True


def attach_file_logging() -> None:
    """(Re)attach the per-run file handler; safe to call repeatedly.

    Called at lifespan startup: uvicorn's default log config replaces the
    root logger's handlers with its own, which would silently drop the run
    log. The file handler goes on root and on uvicorn's configurable loggers
    (`uvicorn`, `uvicorn.error`, `uvicorn.access`), each with
    `propagate=False` (v1.17.6.4) so every record reaches the file exactly
    once no matter whether uvicorn's own config left propagation on or off.
    """
    global _FILE_HANDLER
    if _FILE_HANDLER is None:
        _FILE_HANDLER = _make_file_handler()
    _quiet_http_client_loggers()
    root = logging.getLogger()
    if _FILE_HANDLER not in root.handlers:
        root.addHandler(_FILE_HANDLER)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if _FILE_HANDLER not in logger.handlers:
            logger.addHandler(_FILE_HANDLER)


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
