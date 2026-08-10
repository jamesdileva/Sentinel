"""Sprint 8: OllamaService unit tests (mocked HTTP transport)."""

import httpx
import pytest

from app.services.ollama_service import OllamaService, OllamaUnavailableError


def _service_with(handler) -> OllamaService:
    transport = httpx.MockTransport(handler)
    return OllamaService(host="http://ollama:11434", transport=transport)


def test_generate_returns_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        return httpx.Response(200, json={"response": "hello from gemma2"})

    service = _service_with(handler)
    assert service.generate("hi") == "hello from gemma2"
    service.close()


def test_generate_sends_prompt_and_options():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = request.read()
        return httpx.Response(200, json={"response": "ok"})

    service = _service_with(handler)
    service.generate("prompt text", model="gemma2", max_tokens=123, temperature=0.5)
    import json

    payload = json.loads(captured["payload"])
    assert payload["model"] == "gemma2"
    assert payload["prompt"] == "prompt text"
    assert payload["stream"] is False
    assert payload["options"]["num_predict"] == 123
    assert payload["options"]["temperature"] == 0.5
    service.close()


def test_embed_uses_new_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})
        return httpx.Response(404, json={})

    service = _service_with(handler)
    assert service.embed("text") == [0.1, 0.2, 0.3]
    service.close()


def test_embed_with_metrics_captures_token_counters():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "nomic-embed-text",
                "embeddings": [[0.1, 0.2]],
                "prompt_eval_count": 96,
                "prompt_eval_duration": 48_000_000,
            },
        )

    service = _service_with(handler)
    vector, metrics = service.embed_with_metrics("some text")
    assert vector == [0.1, 0.2]
    assert metrics["tokens"] == 96
    assert metrics["duration_ns"] == 48_000_000
    assert metrics["model"] == "nomic-embed-text"
    service.close()


def test_embed_with_metrics_legacy_returns_zero_counters():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            return httpx.Response(404, json={})
        return httpx.Response(200, json={"embedding": [0.5, 0.6]})

    service = _service_with(handler)
    vector, metrics = service.embed_with_metrics("text")
    assert vector == [0.5, 0.6]
    assert metrics["tokens"] == 0
    assert metrics["duration_ns"] == 0
    service.close()


def test_embed_falls_back_to_legacy_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            return httpx.Response(404, json={})
        if request.url.path == "/api/embeddings":
            return httpx.Response(200, json={"embedding": [0.5, 0.6]})
        return httpx.Response(500, json={})

    service = _service_with(handler)
    assert service.embed("text") == [0.5, 0.6]
    service.close()


def test_is_available():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    service = _service_with(handler)
    assert service.is_available() is True
    service.close()


def test_unavailable_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    service = _service_with(handler)
    with pytest.raises(OllamaUnavailableError):
        service.generate("hi")
    assert service.is_available() is False
    service.close()


def test_list_models():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"models": [{"name": "gemma2:latest"}, {"name": "nomic-embed-text"}]},
        )

    service = _service_with(handler)
    assert service.list_models() == ["gemma2:latest", "nomic-embed-text"]
    service.close()
