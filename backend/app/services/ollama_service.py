"""OllamaService — HTTP client for the local Ollama inference server.

Only talks to the locally configured Ollama host (settings.ollama_host).
Never makes outbound network calls (docs/01 §13: local-first).

Determinism note: embeddings from `nomic-embed-text` are deterministic for a
given input; generation is non-deterministic by nature, so every AI answer
carries provenance (model, timestamp) per docs/01 §16.2.
"""

import httpx

from app.core.config import settings
from app.core.exceptions import OllamaUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


class OllamaService:
    """Thin HTTP client for the Ollama API (generate, embed, tags)."""

    def __init__(
        self,
        host: str | None = None,
        timeout_seconds: int | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.host = (host or settings.ollama_host).rstrip("/")
        self.timeout = timeout_seconds or settings.ollama_timeout_seconds
        self._client = httpx.Client(
            base_url=self.host, timeout=self.timeout, transport=transport
        )

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.3,
        purpose: str = "query",
        num_ctx: int | None = None,
    ) -> str:
        """Generate a text completion for the given prompt."""
        return self.generate_with_metrics(
            prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            purpose=purpose,
            num_ctx=num_ctx,
        )["response"]

    def generate_with_metrics(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.3,
        purpose: str = "query",
        num_ctx: int | None = None,
    ) -> dict:
        """Generate and return text plus Ollama's own perf counters.

        The `metrics` dict carries eval_count / eval_duration / total_duration
        (nanoseconds) as reported by Ollama — used by the System page to show
        tokens/sec without any guesswork (docs/02 §7.3). `purpose` labels what
        the call was for (query / summary / index…) so the activity stream can
        say WHY Ollama is busy (v1.17).
        """
        model = model or settings.ollama_model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                # v1.17.6.6: Ollama's default num_ctx (2048) silently truncates
                # long prompts; raise it so doc-first summary context and
                # all-scope RAG context are never cut off (llama3.1:8b is a
                # 128k-context model, tuned down to settings.ollama_num_ctx).
                # v1.17.12.0: `num_ctx` is overridable — triage keeps it small
                # (4096) because its packet is tiny and a big context slows
                # generation for no gain.
                "num_ctx": num_ctx or settings.ollama_num_ctx,
            },
        }
        try:
            response = self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "response": str(data.get("response", "")).strip(),
                "model": data.get("model") or model,
                "purpose": purpose,
                "eval_count": int(data.get("eval_count") or 0),
                "eval_duration_ns": int(data.get("eval_duration") or 0),
                "total_duration_ns": int(data.get("total_duration") or 0),
            }
        except httpx.HTTPError as exc:
            logger.warning("Ollama generate failed: %s", exc)
            raise OllamaUnavailableError(f"Ollama generate failed: {exc}") from exc

    def embed(self, text: str, model: str | None = None) -> list[float]:
        """Generate an embedding vector for text.

        Uses `/api/embed` (Ollama >= 0.4.0) with a fallback to the legacy
        `/api/embeddings` endpoint.
        """
        return self.embed_with_metrics(text, model=model)[0]

    def embed_with_metrics(
        self, text: str, model: str | None = None
    ) -> tuple[list[float], dict]:
        """Embed and return `(vector, metrics)`.

        The metrics dict carries Ollama's own counters (`tokens` =
        prompt_eval_count, `duration_ns` = prompt_eval_duration or
        total_duration - load_duration when the server omits it — /api/embed
        does NOT return prompt_eval_duration, verified against 0.32.6,
        v1.17.3) so index batches can report tok/s without guesswork
        (v1.17.2). The legacy endpoint returns no counters — metrics are all
        zero then.
        """
        model = model or settings.embedding_model
        payload = {"model": model, "input": text}
        try:
            response = self._client.post("/api/embed", json=payload)
            if response.status_code in (404, 405):
                vector = self._embed_legacy(text, model)
                return vector, {"model": model, "tokens": 0, "duration_ns": 0}
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings") or [data.get("embedding", [])]
            tokens = int(data.get("prompt_eval_count") or 0)
            duration_ns = int(data.get("prompt_eval_duration") or 0)
            if not duration_ns:
                duration_ns = int(data.get("total_duration") or 0) - int(
                    data.get("load_duration") or 0
                )
            metrics = {
                "model": data.get("model") or model,
                "tokens": tokens,
                "duration_ns": duration_ns,
            }
            return list(embeddings[0]), metrics
        except httpx.HTTPError as exc:
            logger.warning("Ollama embed failed: %s", exc)
            raise OllamaUnavailableError(f"Ollama embed failed: {exc}") from exc

    def _embed_legacy(self, text: str, model: str) -> list[float]:
        response = self._client.post(
            "/api/embeddings", json={"model": model, "prompt": text}
        )
        response.raise_for_status()
        return list(response.json().get("embedding", []))

    def is_available(self) -> bool:
        """Check whether the Ollama server is reachable."""
        try:
            response = self._client.get("/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[str]:
        """List installed model names."""
        try:
            response = self._client.get("/api/tags")
            response.raise_for_status()
            return [m.get("name", "") for m in response.json().get("models", [])]
        except httpx.HTTPError as exc:
            logger.warning("Ollama list models failed: %s", exc)
            raise OllamaUnavailableError(f"Ollama list models failed: {exc}") from exc

    def close(self) -> None:
        self._client.close()
