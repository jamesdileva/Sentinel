"""Activity bus tests — persistence, the /system/activity endpoint, and the
live WebSocket broadcast (v1.17)."""

from sqlmodel import Session, func, select

from app.db.connection import get_engine
from app.db.models import ActivityEvent
from app.services import activity_bus


def test_activity_endpoint_returns_persisted_events(client):
    activity_bus.publish_event("sync", "Repo sync: nothing changed")
    activity_bus.publish_event("ollama", "Ollama rag-query for 42 tokens")

    resp = client.get("/api/v1/system/activity")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert events[0]["message"] == "Ollama rag-query for 42 tokens"
    assert events[1]["message"] == "Repo sync: nothing changed"
    assert {e["kind"] for e in events} >= {"sync", "ollama"}


def test_activity_respects_limit(client):
    for i in range(5):
        activity_bus.publish_event("system", f"event-{i}")
    resp = client.get("/api/v1/system/activity?limit=3")
    messages = [e["message"] for e in resp.json()["events"]]
    assert messages == ["event-4", "event-3", "event-2"]


def test_history_is_pruned_to_the_row_ceiling(tmp_db, monkeypatch):
    """v1.17.3 regression: the prune DELETE referenced `activity_event` but
    SQLModel creates `activityevent` — it threw on every publish, so the
    ceiling never ran and a warning was logged per event. The table size
    must stay bounded by _MAX_LIMIT (oldest rows deleted first)."""
    import logging

    monkeypatch.setattr(activity_bus, "_MAX_LIMIT", 3)
    warnings: list[logging.LogRecord] = []
    monkeypatch.setattr(
        activity_bus.logger,
        "warning",
        lambda *args, **kwargs: warnings.append(args),
    )
    for i in range(7):
        activity_bus.publish_event("system", f"event-{i}")

    with Session(get_engine()) as session:
        count = session.exec(select(func.count()).select_from(ActivityEvent)).one()
        rows = session.exec(
            select(ActivityEvent).order_by(ActivityEvent.created_at)
        ).all()
    assert count == 3
    assert [row.message for row in rows] == ["event-4", "event-5", "event-6"]
    assert warnings == []


def test_ws_channel_broadcasts_activity(client):
    with client.websocket_connect("/api/v1/ws/jobs") as ws:
        welcome = ws.receive_json()
        assert welcome["type"] == "welcome"

        activity_bus.publish_event("job", "run_build running")

        frame = ws.receive_json()
        assert frame["type"] == "activity"
        assert frame["event"]["message"] == "run_build running"
