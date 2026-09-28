"""
websocket_manager.py
Purpose: True real-time push updates via WebSockets (the third of the
three approaches your project brief lists: Polling / SSE / WebSockets-
or-cloud-realtime-DB). Clients open one WebSocket per event
(`/ws/events/{event_id}`) and receive a message the instant anyone's
RSVP changes for that event - no polling interval, no manual refresh.

This is the direct FastAPI analogue of a Firestore `onSnapshot`
listener: `rsvp_service` calls `manager.broadcast(event_id, payload)`
right after committing a transaction, and every connected browser for
that event gets the new counts pushed to it immediately.
"""

import json
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # event_id -> set of live WebSocket connections watching that event
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, event_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(event_id, set()).add(websocket)

    def disconnect(self, event_id: str, websocket: WebSocket):
        conns = self.active_connections.get(event_id)
        if conns and websocket in conns:
            conns.remove(websocket)
        if conns is not None and not conns:
            self.active_connections.pop(event_id, None)

    async def broadcast(self, event_id: str, message: dict):
        """Push `message` to every client currently watching this event.
        Dead connections are pruned silently (failure handling: a client
        that disconnected mid-broadcast just gets dropped from the set,
        not treated as a server error)."""
        conns = list(self.active_connections.get(event_id, []))
        dead = []
        for ws in conns:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(event_id, ws)


manager = ConnectionManager()
