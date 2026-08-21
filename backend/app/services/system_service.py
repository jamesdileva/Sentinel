"""SystemService — read-only home status aggregation (Sprint 12).

Surface: GET /api/v1/system/* reports the health of the services Sentinel
integrates with (Ollama) plus backend startup checks. Strictly read-only
(docs/01 Rule 2: AI/actions are never autonomous) — nothing here toggles
blocking or starts/stops/loads models.

Ollama "tokens/sec" is derived deterministically from Ollama's own
eval_count / eval_duration counters, persisted for every generation
(see OllamaQueryLog).
"""

import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import OllamaQueryLog
from app.services.ollama_service import OllamaService
from app.services.startup_check import ComponentStatus, run_startup_checks

logger = get_logger(__name__)


def _dt(value: datetime.datetime) -> str:
    """Serialize timestamps with an explicit UTC offset.

    Rows are stored naive-UTC; a bare `isoformat()` has no offset and browsers
    parse it as *local* time (the v1.17 sync pill showed UTC wall-clock
    numbers instead of the machine's timezone).
    """
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc).isoformat()
    return value.isoformat() if value is not None else ""


def _tokens_per_second(row: OllamaQueryLog) -> float | None:
    """eval_count / eval_duration → tokens/sec; None when not measurable."""
    if row.eval_duration_ns <= 0:
        return None
    return round(row.eval_count / (row.eval_duration_ns / 1e9), 1)


class OllamaStatus:
    """Live Ollama state plus recent deterministic generation records."""

    def __init__(self, session: Session | None = None) -> None:
        self.session = session
        # v1.17.18.3 (audit2 S1): created lazily — record_query()-only callers
        # (rag/triage provenance logging) must not build an unused httpx pool.
        self.ollama: OllamaService | None = None

    def _ensure_ollama(self) -> OllamaService:
        if self.ollama is None:
            self.ollama = OllamaService()
        return self.ollama

    def report(self) -> dict:
        try:
            ollama = self._ensure_ollama()
            available = ollama.is_available()
            models: list[str] = []
            if available:
                try:
                    models = ollama.list_models()
                except Exception:  # noqa: BLE001  probe only
                    models = []
        finally:
            # v1.17.18.3 (audit2 S1): OllamaStatus is built per request;
            # without an explicit close each poll leaked an httpx pool.
            if self.ollama is not None:
                self.ollama.close()
        return {
            "available": available,
            "host": settings.ollama_host,
            "model_default": settings.ollama_model,
            "models": models,
            "recent": self.recent_queries(),
        }

    def record_query(
        self,
        model: str,
        prompt: str,
        response: str,
        eval_count: int,
        eval_duration_ns: int,
        total_duration_ns: int,
        purpose: str = "query",
    ) -> None:
        """Persist a deterministic record of an Ollama call (no AI)."""
        if self.session is None:
            return
        self.session.add(
            OllamaQueryLog(
                model=model,
                purpose=purpose,
                prompt_chars=len(prompt),
                response_chars=len(response),
                eval_count=eval_count,
                eval_duration_ns=eval_duration_ns,
                total_duration_ns=total_duration_ns,
            )
        )
        self.session.commit()

    def recent_queries(self, limit: int | None = None) -> list[dict]:
        if self.session is None:
            return []
        limit = limit or settings.max_recent_ollama_queries
        try:
            # v1.17.18.3 (audit2 Q6): ORDER BY + LIMIT in SQL — this table
            # grows forever (a row per generation), and materializing every
            # row to sort in Python degraded /system/* linearly with usage.
            rows = list(
                self.session.exec(
                    select(OllamaQueryLog)
                    .order_by(col(OllamaQueryLog.created_at).desc())
                    .limit(limit)
                )
            )
        except SQLAlchemyError:
            # Defensive (v1.17.1): a pre-migration DB without newer columns
            # (e.g. ollama_query_log.purpose) must degrade to empty, not 500.
            logger.warning(
                "Ollama query log read failed (schema not migrated yet?)",
                exc_info=True,
            )
            return []
        return [
            {
                "model": row.model,
                "purpose": row.purpose,
                "prompt_chars": row.prompt_chars,
                "response_chars": row.response_chars,
                "eval_count": row.eval_count,
                "eval_duration_ns": row.eval_duration_ns,
                "total_duration_ns": row.total_duration_ns,
                "tokens_per_second": _tokens_per_second(row),
                "latency_ms": (
                    round(row.total_duration_ns / 1_000_000, 1)
                    if row.total_duration_ns
                    else 0
                ),
                "created_at": _dt(row.created_at),
            }
            for row in rows[:limit]
        ]


def system_overview(session: Session | None = None) -> dict:
    """Aggregate report for GET /api/v1/system/overview."""
    states: list[ComponentStatus] = run_startup_checks()
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "startup": {
            "states": [
                {
                    "name": state.name,
                    "ok": bool(state.ok),
                    "detail": state.detail,
                }
                for state in states
            ]
        },
        "ollama": OllamaStatus(session=session).report(),
    }
