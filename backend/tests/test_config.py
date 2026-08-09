"""Settings defaults: watch dirs must follow the machine, not the dev box."""

from pathlib import Path

from app.core.config import Settings


def test_watch_dirs_default_to_home_directory():
    fresh = Settings(_env_file=None)
    assert fresh.watch_dirs == [str(Path.home())]
