"""Sprint 11: exception classes + WebSocket channel coverage.

app/core/exceptions.py defines the domain error hierarchy (currently no API
handlers are registered, so the classes are exercised directly). ws.py is
covered through a real TestClient WebSocket session including the heartbeat
loop and disconnect path.
"""

from fastapi.testclient import TestClient

from app.core.exceptions import (
    ConfigurationError,
    NotFoundError,
    OllamaUnavailableError,
    SentinelError,
)
from app.main import app


def test_sentinel_error_defaults():
    assert SentinelError().status_code == 400
    assert isinstance(SentinelError("boom"), Exception)


def test_not_found_status():
    assert NotFoundError.status_code == 404


def test_configuration_status():
    assert ConfigurationError.status_code == 500


def test_ollama_unavailable_status():
    assert OllamaUnavailableError.status_code == 503


def test_ws_welcome_then_heartbeat_then_close(tmp_db, monkeypatch):
    import app.api.v1.ws as ws_module

    monkeypatch.setattr(ws_module, "_HEARTBEAT_SECONDS", 0.05)
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/jobs") as websocket:
            welcome = websocket.receive_json()
            assert welcome["type"] == "welcome"
            assert welcome["channel"] == "jobs"
            heartbeat = websocket.receive_json()
            assert heartbeat == {"type": "heartbeat"}
            websocket.close()
