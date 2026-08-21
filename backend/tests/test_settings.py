"""Settings page — /api/v1/settings endpoints (v1.17.18.0).

Read-only configuration report: every SENTINEL_* setting with value / default /
source, secrets redacted, and deterministic validation warnings. No writes.
"""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import settings_service


class _FakeOllama:
    """Deterministic stand-in for the Ollama probe (never touches the network)."""

    def __init__(self, available=True, models=("nomic-embed-text",)):
        self._available = available
        self._models = models

    def is_available(self):
        return self._available

    def list_models(self):
        return list(self._models)


def _report(tmp_db, monkeypatch, ollama=None, **overrides):
    monkeypatch.setattr(
        settings_service,
        "OllamaService",
        lambda **kw: ollama if ollama is not None else _FakeOllama(),
    )
    for key, value in overrides.items():
        monkeypatch.setattr(settings, key, value)
    with TestClient(app) as client:
        return client.get("/api/v1/settings"), client


def test_settings_lists_all_groups_and_items(tmp_db, monkeypatch):
    response, _ = _report(tmp_db, monkeypatch)
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == settings.version
    groups = {g["name"]: g["items"] for g in body["groups"]}
    assert set(groups) == {"Server", "Paths", "AI", "Ops", "World Sim"}
    keys = {item["key"] for items in groups.values() for item in items}
    assert "SENTINEL_PORT" in keys
    assert "SENTINEL_DB_PATH" in keys
    assert "SENTINEL_OLLAMA_MODEL" in keys


def test_secrets_are_redacted(tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "github_token", "ghp_super-secret")
    response, _ = _report(tmp_db, monkeypatch)
    body = response.json()
    items = {i["key"]: i for g in body["groups"] for i in g["items"]}
    assert items["SENTINEL_GITHUB_TOKEN"]["value"] == "set"
    assert "super-secret" not in response.text


def test_secret_unset_shows_not_set(tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "github_token", "")
    response, _ = _report(tmp_db, monkeypatch)
    body = response.json()
    items = {i["key"]: i for g in body["groups"] for i in g["items"]}
    assert items["SENTINEL_GITHUB_TOKEN"]["value"] == "not set"


def test_source_reflects_env_override(tmp_db, monkeypatch):
    monkeypatch.setenv("SENTINEL_PORT", "9000")
    monkeypatch.setattr(settings, "port", 9000)
    response, _ = _report(tmp_db, monkeypatch)
    body = response.json()
    port = next(
        i for g in body["groups"] for i in g["items"] if i["key"] == "SENTINEL_PORT"
    )
    assert port["value"] == "9000"
    assert port["source"] == "env"


def test_warnings_on_bad_config(tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "port", 99999)
    fake = _FakeOllama(available=False)
    response, _ = _report(tmp_db, monkeypatch, ollama=fake)
    body = response.json()
    keys = {w["key"] for w in body["warnings"]}
    assert "port" in keys
    assert "ollama" in keys


def test_embedding_model_warning_when_missing(tmp_db, monkeypatch):
    fake = _FakeOllama(models=("llama3.1:latest",))
    response, _ = _report(tmp_db, monkeypatch, ollama=fake)
    body = response.json()
    keys = {w["key"] for w in body["warnings"]}
    assert "embedding_model" in keys


def test_embedding_model_present_with_latest_tag(tmp_db, monkeypatch):
    """Ollama reports installed models as `nomic-embed-text:latest`; the
    config name without the tag must NOT warn (they are the same model)."""
    fake = _FakeOllama(models=("nomic-embed-text:latest", "llama3.1:8b"))
    response, _ = _report(tmp_db, monkeypatch, ollama=fake)
    body = response.json()
    keys = {w["key"] for w in body["warnings"]}
    assert "embedding_model" not in keys
