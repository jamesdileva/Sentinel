"""Custom exceptions and FastAPI exception handlers."""


class SentinelError(Exception):
    """Base class for all Sentinel domain errors."""

    status_code = 400


class NotFoundError(SentinelError):
    status_code = 404


class ConfigurationError(SentinelError):
    status_code = 500


class OllamaUnavailableError(SentinelError):
    status_code = 503
