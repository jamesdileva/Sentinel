"""WebSocket endpoints — live job updates for the dashboard.

Sprint 6 wires the transport; Sprint 7 publishes real build/test/scan events.
Until then the channel sends a welcome frame and a heartbeat every 30s so
clients can verify connectivity and reconnect behavior.
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

_HEARTBEAT_SECONDS = 30


@router.websocket("/ws/jobs")
async def jobs_ws(websocket: WebSocket) -> None:
    """Live job-status channel. Clients receive a welcome frame then heartbeats."""
    await websocket.accept()
    await websocket.send_json(
        {"type": "welcome", "channel": "jobs", "message": "connected"}
    )
    try:
        while True:
            await asyncio.sleep(_HEARTBEAT_SECONDS)
            await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        return
