"""
WebSocket event broadcaster for the companion inventory app.
Manages per-session WebSocket connections and broadcasts events to all listeners.
"""

from fastapi import WebSocket
import asyncio
import json


class ConnectionManager:
    def __init__(self):
        # session_id -> list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if session_id not in self._connections:
            self._connections[session_id] = []
        self._connections[session_id].append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(session_id, [])
        if websocket in conns:
            conns.remove(websocket)

    async def broadcast(self, session_id: str, event_type: str, data: dict) -> None:
        """Send an event to all companion clients watching this session."""
        payload = json.dumps({"type": event_type, "data": data})
        dead = []
        for ws in self._connections.get(session_id, []):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)


manager = ConnectionManager()


def broadcast_sync(session_id: str, event_type: str, data: dict) -> None:
    """
    Fire-and-forget broadcast from synchronous route handlers.
    Creates a new event loop task if one is running, otherwise does nothing.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast(session_id, event_type, data))
    except RuntimeError:
        pass
