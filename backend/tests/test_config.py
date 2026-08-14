"""Settings: repo-root .env is the single source of overrides, and watch dirs
follow the machine, not the dev box."""

from pathlib import Path

from app.core.config import BASE_DIR, Settings


def test_env_file_points_at_repo_root():
    assert Settings.model_config["env_file"] == BASE_DIR / ".env"


def test_watch_dirs_default_to_home_directory():
    fresh = Settings(_env_file=None)
    assert fresh.watch_dirs == [str(Path.home())]


def test_watch_dirs_accepts_single_and_comma_separated_values(tmp_path):
    """v1.17.7.3: the documented comma-separated format used to crash
    pydantic-settings' JSON-only complex-field parser (SettingsError); plain
    single and comma-separated values must parse into a directory list."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SENTINEL_WATCH_DIRS=C:\\Users\\j,C:\\Users\\j\\projects\n",
        encoding="utf-8",
    )
    fresh = Settings(_env_file=env_file)
    assert fresh.watch_dirs == [r"C:\Users\j", r"C:\Users\j\projects"]
    env_file.write_text(
        "SENTINEL_WATCH_DIRS=C:\\Users\\j\\projects\n", encoding="utf-8"
    )
    fresh = Settings(_env_file=env_file)
    assert fresh.watch_dirs == [r"C:\Users\j\projects"]


def test_watch_dirs_accepts_json_array_when_set_directly(monkeypatch):
    """Direct env vars (Task Scheduler, shells) may use the JSON form —
    backslashes are legal JSON there since dotenv is not involved."""
    monkeypatch.setenv(
        "SENTINEL_WATCH_DIRS", r'["C:\\Users\\j", "C:\\Users\\j\\projects"]'
    )
    fresh = Settings(_env_file=None)
    assert fresh.watch_dirs == [r"C:\Users\j", r"C:\Users\j\projects"]


def test_sync_interval_defaults_to_daily():
    """v1.17.1: repo sync runs on startup, then once a day (was every 15 min);
    the header 'Sync now' button covers anything in between."""
    fresh = Settings(_env_file=None)
    assert fresh.sync_interval_minutes == 1440


def test_scan_interval_defaults_to_daily():
    """v1.17.7: the security scan-all beat owns its own daily schedule,
    independent of the (optional) GitHub sync."""
    fresh = Settings(_env_file=None)
    assert fresh.scan_interval_minutes == 1440


def test_scan_interval_loads_from_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SENTINEL_SCAN_INTERVAL_MINUTES=60\n", encoding="utf-8")
    fresh = Settings(_env_file=env_file)
    assert fresh.scan_interval_minutes == 60


def test_world_sim_disabled_by_default():
    """v1.17.7.3: the world simulator is opt-in — the router and beat
    register only when SENTINEL_WORLD_SIM_ENABLED=true."""
    fresh = Settings(_env_file=None)
    assert fresh.world_sim_enabled is False


def test_values_load_from_dotenv_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SENTINEL_PORT=8123\nSENTINEL_GITHUB_TOKEN=ghp_test_token\n",
        encoding="utf-8",
    )
    fresh = Settings(_env_file=env_file)
    assert fresh.port == 8123
    assert fresh.github_token == "ghp_test_token"
