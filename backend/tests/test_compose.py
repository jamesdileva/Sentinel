"""Sprint 4: Docker Compose orchestration validation tests.

These tests validate the compose configuration and dev helper deterministically
without requiring a running Docker daemon.
"""

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "docker-compose.yml"
OVERRIDE = REPO_ROOT / "docker-compose.override.yml"
DOCKERFILE = REPO_ROOT / "docker" / "backend" / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
DEV_PY = REPO_ROOT / "scripts" / "dev.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dev  # noqa: E402


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_compose_defines_core_services():
    compose = _load(COMPOSE)
    assert {"backend", "redis"} <= set(compose["services"])
    assert compose["services"]["redis"]["image"] == "redis:7-alpine"


def test_compose_backend_environment():
    backend = _load(COMPOSE)["services"]["backend"]
    env = backend["environment"]
    assert env["SENTINEL_DB_PATH"] == "/data/sqlite/sentinel.db"
    assert env["SENTINEL_CHROMA_PATH"] == "/data/chroma"
    # Sprint 8.5: AI is served by the laptop's shared Ollama over the LAN
    assert env["SENTINEL_OLLAMA_HOST"] == "http://192.168.4.40:11434"
    assert env["SENTINEL_WATCH_DIRS"] == '["/data/projects"]'


def test_compose_pihole_profile_and_ports():
    compose = _load(COMPOSE)
    pihole = compose["services"]["pihole"]
    assert pihole["profiles"] == ["pihole"]
    assert pihole["image"] == "ghcr.io/pi-hole/pihole:latest"
    assert "53:53/tcp" in pihole["ports"]
    assert "53:53/udp" in pihole["ports"]
    assert "8053:80/tcp" in pihole["ports"]


def test_compose_pihole_environment():
    pihole = _load(COMPOSE)["services"]["pihole"]
    env = pihole["environment"]
    assert env["FTLCONF_LOCAL_IPV4"] == "192.168.4.40"
    assert env["FTLCONF_webpassword"] == "${PIHOLE_WEBPASSWORD}"
    assert env["TZ"] == "${PIHOLE_TZ:-UTC}"


def test_compose_backend_mounts_data():
    backend = _load(COMPOSE)["services"]["backend"]
    assert "./data:/data" in backend["volumes"]
    assert "8000:8000" in backend["ports"]


def test_ollama_is_optional_profile():
    compose = _load(COMPOSE)
    ollama = compose["services"]["ollama"]
    assert ollama["profiles"] == ["ollama"]


def test_override_enables_dev_mode():
    override = _load(OVERRIDE)
    backend = override["services"]["backend"]
    assert "--reload" in backend["command"]
    assert "./backend:/app" in backend["volumes"]


def test_dockerfile_slim_and_uvicorn_cmd():
    content = DOCKERFILE.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in content
    assert 'CMD ["uvicorn", "app.main:app"' in content


def test_dockerignore_excludes_venv_and_data():
    content = DOCKERIGNORE.read_text(encoding="utf-8")
    assert ".venv/" in content
    assert "data/" in content
    assert "__pycache__/" in content


def test_dev_py_up_command():
    args = dev.build_parser().parse_args([])
    cmd = dev.compose_command(args)
    assert cmd[-3:] == ["up", "-d", "--build"]


def test_dev_py_down_command():
    args = dev.build_parser().parse_args(["--down"])
    cmd = dev.compose_command(args)
    assert cmd[-1] == "down"
    assert "up" not in cmd


def test_dev_py_backend_only_and_ollama_profile():
    args = dev.build_parser().parse_args(["--backend-only", "--with-ollama"])
    cmd = dev.compose_command(args)
    assert cmd[2:4] == ["--profile", "ollama"]
    assert cmd[-1] == "backend"
