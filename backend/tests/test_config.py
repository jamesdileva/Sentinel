"""Settings: repo-root .env is the single source of overrides, and watch dirs
follow the machine, not the dev box."""

from pathlib import Path

from app.core.config import BASE_DIR, Settings


def test_env_file_points_at_repo_root():
    assert Settings.model_config["env_file"] == BASE_DIR / ".env"


def test_watch_dirs_default_to_home_directory():
    fresh = Settings(_env_file=None)
    assert fresh.watch_dirs == [str(Path.home())]


def test_sync_interval_defaults_to_daily():
    """v1.17.1: repo sync runs on startup, then once a day (was every 15 min);
    the header 'Sync now' button covers anything in between."""
    fresh = Settings(_env_file=None)
    assert fresh.sync_interval_minutes == 1440


def test_values_load_from_dotenv_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SENTINEL_PORT=8123\nSENTINEL_GITHUB_TOKEN=ghp_test_token\n",
        encoding="utf-8",
    )
    fresh = Settings(_env_file=env_file)
    assert fresh.port == 8123
    assert fresh.github_token == "ghp_test_token"
