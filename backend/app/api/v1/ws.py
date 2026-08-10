"""WebSocket endpoints — live activity for the dashboard (Sprint 6+, v1.17).

The channel previously sent welcome + heartbeat only; since v1.17 the
in-process activity bus broadcasts every notable event (sync, indexing,
builds, scans, Ollama usage) to connected clients. A heartbeat every 30s
lets clients verify connectivity when no events are flowing.
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services import activity_bus

router = APIRouter(tags=["websocket"])

_HEARTBEAT_SECONDS = 30


@router.websocket("/ws/jobs")
async def jobs_ws(websocket: WebSocket) -> None:
    """Live activity channel. Welcome frame first, then events + heartbeats."""
    await websocket.accept()
    await websocket.send_json(
        {"type": "welcome", "channel": "jobs", "message": "connected"}
    )
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    activity_bus.subscribe(loop, queue)
    try:
        while True:
            try:
                frame = await asyncio.wait_for(queue.get(), _HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
                continue
            await websocket.send_json(frame)
    except WebSocketDisconnect:
        pass
    finally:
        activity_bus.unsubscribe(loop, queue)
