"""Custom exceptions and FastAPI exception handlers.

v1.17.18.3 (audit2 Q3): the hierarchy is now wired — main.py registers a
central handler for SentinelError that maps each subclass's status_code to
the response, so every route gets consistent status codes for identical
failures (previously Ollama unavailability was 503 from sessions but an
unhandled 500 from /rag/*).
"""


class SentinelError(Exception):
    """Base class for all Sentinel domain errors."""

    status_code = 400


class NotFoundError(SentinelError):
    status_code = 404


class ConfigurationError(SentinelError):
    status_code = 500


class OllamaUnavailableError(SentinelError):
    """Raised when the Ollama server cannot be reached or returns an error.

    Defined here (single definition) and raised by ollama_service /
    triage_service; the central handler in app.main turns it into a 503.
    """

    status_code = 503
