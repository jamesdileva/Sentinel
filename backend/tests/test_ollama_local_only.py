"""Audit A5: Rule 1 enforcement for the configured Ollama host."""

import httpx
import pytest

from app.core.config import is_loopback_host, settings
from app.core.exceptions import LocalOnlyViolationError
from app.services.ollama_service import OllamaService

LOOPBACK = [
    "http://localhost:11434",
    "http://127.0.0.1:11434",
    "http://127.8.9.10:11434",  # whole 127/8 is loopback
    "http://[::1]:11434",
    "http://localhost",
    "127.0.0.1:11434",  # bare host:port, no scheme
    "::1",
    "http://LOCALHOST:11434",
    "http://localhost.",  # trailing root dot
]

REMOTE = [
    "http://192.168.1.50:11434",
    "http://10.0.0.2:11434",
    "http://ollama.lan:11434",
    "http://example.com",
    "https://gpu-box.example.net:443",
    "http://0.0.0.0:11434",  # not loopback — it is "everywhere"
    "http://[::2]:11434",
    "garbage",
    "",
]


@pytest.mark.parametrize("host", LOOPBACK)
def test_loopback_hosts_accepted(host):
    assert is_loopback_host(host) is True


@pytest.mark.parametrize("host", REMOTE)
def test_remote_hosts_rejected(host):
    assert is_loopback_host(host) is False


def test_ipv4_mapped_ipv6_is_loopback():
    assert is_loopback_host("http://[::ffff:127.0.0.1]:11434") is True


def test_default_host_is_loopback():
    assert is_loopback_host(settings.ollama_host) is True


def test_service_constructs_with_default_loopback_host():
    # The default configuration must never raise.
    OllamaService(timeout_seconds=2).close()


def test_service_refuses_remote_host_from_config(tmp_db, monkeypatch):
    """The client itself is the enforcement point: with a non-loopback host in
    configuration, no request can be made at all — that is the Rule 1
    guarantee, not a warning."""
    monkeypatch.setattr(settings, "ollama_host", "http://192.168.1.50:11434")
    with pytest.raises(LocalOnlyViolationError):
        OllamaService()


def test_service_allows_remote_host_when_opted_in(tmp_db, monkeypatch):
    monkeypatch.setattr(settings, "ollama_host", "http://192.168.1.50:11434")
    monkeypatch.setattr(settings, "allow_remote_ollama", True)
    # Explicit opt-in constructs (it will fail to connect, which is fine).
    service = OllamaService(timeout_seconds=2)
    try:
        assert service.host.startswith("http://192.168.1.50")
    finally:
        service.close()


def test_explicit_host_is_the_callers_choice():
    """Tests/tooling inject their own host; the loopback rule is about
    configuration, not the constructor's arguments."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    service = OllamaService(
        host="http://ollama.test:11434", transport=httpx.MockTransport(handler)
    )
    try:
        assert service.is_available() is True
    finally:
        service.close()
