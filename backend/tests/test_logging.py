"""v1.17.6.3: per-run log file (data/logs/sentinel.log) tests.

The file answers "what happened this run": truncated at startup, INFO level,
capturing console-equivalent detail plus uvicorn's own loggers.
"""

import logging
from pathlib import Path

from app.core import logging as core_logging
from app.core.logging import attach_file_logging, run_log_path, setup_logging


def test_setup_logging_writes_run_log(tmp_path, monkeypatch):
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    monkeypatch.setattr(core_logging, "_CONFIGURED", False, raising=False)
    monkeypatch.setattr(core_logging, "_FILE_HANDLER", None, raising=False)
    monkeypatch.setattr(core_logging, "_CONSOLE_HANDLER", None, raising=False)
    from app.core.config import settings

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    try:
        setup_logging(logging.INFO)
        logger = core_logging.get_logger("tests.run_log")
        logger.info("hello run log")
        logger.debug("debug line is too noisy for the file")
        logger.warning("warning line")
        content = run_log_path().read_text(encoding="utf-8")
    finally:
        root.handlers = previous_handlers
    assert "hello run log" in content
    assert "warning line" in content
    assert "debug line is too noisy for the file" not in content
    assert Path(run_log_path()).parent.is_dir()


def test_run_log_uses_overwrite_mode(tmp_path, monkeypatch):
    """v1.17.6.3: the run log is per-run — `mode="w"` truncates the previous
    run's file when the app starts (the "what happened this run" contract).
    Asserted via the handler's mode + path (deterministic) and a settled
    read of the file's content."""
    import time

    from app.core.config import settings

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    path = run_log_path()
    path.parent.mkdir(parents=True)
    path.write_text("stale previous run", encoding="utf-8")
    handler = core_logging._make_file_handler()
    try:
        assert handler.mode == "w"
        assert Path(handler.baseFilename) == path
        handler.stream.write("fresh run marker\n")
        handler.flush()
    finally:
        handler.close()
    time.sleep(0.2)  # let NTFS settle the end-of-file update
    assert "fresh run marker" in path.read_text(encoding="utf-8")


def test_attach_file_logging_is_idempotent(tmp_path, monkeypatch):
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    from app.core.config import settings

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    monkeypatch.setattr(core_logging, "_FILE_HANDLER", None, raising=False)
    try:
        attach_file_logging()
        attach_file_logging()
        matching = [
            h
            for h in root.handlers
            if isinstance(h, logging.FileHandler)
            and h.baseFilename == str(run_log_path())
        ]
        assert len(matching) == 1, "the run-log handler must never duplicate"
        # v1.17.6.4: root holds the file handler for app loggers; the uvicorn
        # loggers carry it too, each pinned with propagate=False, so a record
        # is written exactly once regardless of uvicorn's own config.
        for name, expected in (
            ("uvicorn", 1),
            ("uvicorn.error", 1),
            ("uvicorn.access", 1),
        ):
            logger = logging.getLogger(name)
            assert logger.propagate is False, f"{name} must not propagate"
            attached = [
                h
                for h in logger.handlers
                if isinstance(h, logging.FileHandler)
                and h.baseFilename == str(run_log_path())
            ]
            assert len(attached) == expected, (
                f"{name} should carry the run-log handler "
                f"{expected} times, found {len(attached)}"
            )
        logger = core_logging.get_logger("tests.attach")
        logger.info("after attach")
        # a uvicorn.error record lands in the file exactly once.
        logging.getLogger("uvicorn.error").error("single error copy")
        # an app-logger record lands exactly once too (root handler only).
        logging.getLogger("app.core.logging").info("single app copy")
    finally:
        root.handlers = previous_handlers
    content = run_log_path().read_text(encoding="utf-8")
    assert "after attach" in content
    assert content.count("single error copy") == 1
    assert content.count("single app copy") == 1


def test_httpx_httpcore_silenced_to_warning(tmp_path, monkeypatch):
    """v1.17.6.4: httpx/httpcore loggers are set to WARNING so the run log
    stops filling with one `POST /api/embed` line per HTTP call — that
    detail already lives in the activity feed and the Ollama query log."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "chroma_path", tmp_path / "shared")
    monkeypatch.setattr(core_logging, "_CONFIGURED", False, raising=False)
    monkeypatch.setattr(core_logging, "_FILE_HANDLER", None, raising=False)
    monkeypatch.setattr(core_logging, "_CONSOLE_HANDLER", None, raising=False)
    previous_handlers = list(logging.getLogger().handlers)
    try:
        setup_logging(logging.INFO)
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
    finally:
        logging.getLogger().handlers = previous_handlers
