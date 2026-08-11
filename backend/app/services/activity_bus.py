"""In-process activity bus — live events + bounded history (v1.17).

Services publish notable events (sync runs, knowledge indexing, builds,
security scans, Ollama generations) through `publish_event`. Every event is:

1. written to the `activity_event` table (pruned to `_MAX_LIMIT` rows) so
   restarts don't lose history,
2. fanned out to every WebSocket subscriber on /api/v1/ws/jobs so the
   dashboard can show activity while it happens.

Thread-safe by construction (jobs run in scheduler threads, WS handlers run
on the event loop); SQLite is a single writer, so persistence is serialized
with a lock and is strictly best-effort — a failed insert never disrupts the
event or the caller. Deterministic per Project Rule 3.
"""

import asyncio
import datetime
import threading
from collections import deque
from typing import Any

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.db.connection import get_engine
from app.db.models import ActivityEvent

logger = get_logger(__name__)

_MAX_LIMIT = 5000  # persisted history ceiling
_IN_MEMORY_TAIL = 100  # served instantly before a DB read matters

_PERSIST_LOCK = threading.Lock()
_MEMORY_TAIL: deque[dict] = deque(maxlen=_IN_MEMORY_TAIL)
_SUBSCRIBERS: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def publish_event(
    kind: str,
    message: str,
    detail: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict:
    """Record one activity event and broadcast it to open WebSockets."""
    event: dict[str, Any] = {
        "kind": kind,
        "message": message,
        "detail": detail,
        "data": data,
        "created_at": _now_iso(),
    }
    _MEMORY_TAIL.append(event)
    try:  # persistence is best-effort
        engine = get_engine()
        with _PERSIST_LOCK:
            with Session(engine) as session:
                session.add(
                    ActivityEvent(
                        kind=event["kind"],
                        message=event["message"],
                        detail=event.get("detail"),
                        data=event.get("data"),
                    )
                )
                session.commit()
            with engine.begin() as conn:
                # v1.17.3: SQLModel names the table `activityevent` (class
                # name, no underscore) — the previous hard-coded
                # `activity_event` made this DELETE fail on *every* publish,
                # spamming warnings and never enforcing the row ceiling.
                table = ActivityEvent.__tablename__
                conn.exec_driver_sql(
                    f'DELETE FROM "{table}" WHERE rowid NOT IN ('
                    f'SELECT rowid FROM "{table}" '
                    "ORDER BY rowid DESC LIMIT ?)",
                    (_MAX_LIMIT,),
                )
    except Exception:  # noqa: BLE001 — history must never break the publisher
        # v1.17.2: was debug — a failing writer made the dashboard history
        # silently disappear (live frames still flow, reads return stale
        # rows). A warn makes the data-loss condition visible in the log.
        logger.warning("activity persist failed (non-fatal)", exc_info=True)
    frame = {"type": "activity", "event": event}
    for loop, queue in tuple(_SUBSCRIBERS):
        try:
            loop.call_soon_threadsafe(queue.put_nowait, frame)
        except RuntimeError:
            _SUBSCRIBERS.discard((loop, queue))
    return event


def subscribe(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
    """Register a WebSocket client queue; it receives every future frame."""
    _SUBSCRIBERS.add((loop, queue))


def unsubscribe(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
    _SUBSCRIBERS.discard((loop, queue))


def recent_events(limit: int = 50) -> list[dict]:
    """Tail of the persisted history, newest first (System activity endpoint)."""
    try:
        with Session(get_engine()) as session:
            rows = session.exec(
                select(ActivityEvent)
                .order_by(ActivityEvent.created_at.desc())
                .limit(limit)
            ).all()
            return [
                {
                    "id": row.id,
                    "kind": row.kind,
                    "message": row.message,
                    "detail": row.detail,
                    "data": row.data or {},
                    "created_at": _iso_utc(row.created_at),
                }
                for row in rows
            ]
    except Exception:  # noqa: BLE001 — transient failures degrade to memory tail
        logger.debug("activity fetch failed, falling back to memory", exc_info=True)
        return list(_MEMORY_TAIL)[::-1]


def _iso_utc(value: datetime.datetime | None) -> str:
    """Serialize a stored (naive UTC) timestamp with an explicit offset so
    browsers render it in the user's local timezone, not UTC wall-clock."""
    if value is None:
        return ""
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc).isoformat()
    return value.isoformat()
