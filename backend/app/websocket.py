"""WebSocket Management Module.

This module provides WebSocket connection management for pushing real-time status updates to clients.
"""

# Standard library imports
import datetime as dt
from typing import Any, Dict, List

# Third-party library imports
from fastapi import WebSocket


class ConnectionManager:
    """WebSocket connection manager, responsible for handling client connections and broadcasting messages."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: List[WebSocket] = []
        self._connection_meta: Dict[int, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket):
        """Accept and save WebSocket connection.

        Args:
            websocket: WebSocket connection object.
        """
        await websocket.accept()
        self.active_connections.append(websocket)

        client_host = None
        client_port = None
        if websocket.client:
            client_host, client_port = websocket.client

        scope_path = websocket.scope.get("path") if hasattr(websocket, "scope") else None

        connected_at = dt.datetime.now(dt.timezone.utc)
        connection_id = id(websocket)
        self._connection_meta[connection_id] = {
            "client_host": client_host,
            "client_port": client_port,
            "connected_at": connected_at,
            "path": scope_path,
            "status": "connected",
        }

    def disconnect(self, websocket: WebSocket):
        """Disconnect WebSocket connection.

        Args:
            websocket: WebSocket connection object.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        self._connection_meta.pop(id(websocket), None)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all active connections.

        Args:
            message: Message to broadcast.
        """
        for connection in self.active_connections:
            await connection.send_json(message)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send personal message to specific connection.

        Args:
            message: Message to send.
            websocket: WebSocket connection to receive the message.
        """
        await websocket.send_json(message)

    def list_connections(self) -> List[Dict[str, Any]]:
        """Return metadata for active WebSocket connections."""
        summaries: List[Dict[str, Any]] = []
        now = dt.datetime.now(dt.timezone.utc)

        for connection in self.active_connections:
            connection_id = id(connection)
            meta = self._connection_meta.get(connection_id, {})
            connected_at: dt.datetime | None = meta.get("connected_at")
            uptime_seconds = None
            connected_at_iso = None
            if isinstance(connected_at, dt.datetime):
                uptime_seconds = (now - connected_at).total_seconds()
                connected_at_iso = connected_at.isoformat()

            summaries.append(
                {
                    "connection_id": connection_id,
                    "client_host": meta.get("client_host"),
                    "client_port": meta.get("client_port"),
                    "connected_at": connected_at_iso,
                    "uptime_seconds": uptime_seconds,
                    "status": meta.get("status", "connected"),
                    "path": meta.get("path"),
                }
            )

        return summaries


# Create connection manager instance
manager = ConnectionManager()