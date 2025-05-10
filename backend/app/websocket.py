"""WebSocket Management Module.

This module provides WebSocket connection management for pushing real-time status updates to clients.
"""

# Standard library imports
from typing import Any, Dict, List

# Third-party library imports
from fastapi import WebSocket


class ConnectionManager:
    """WebSocket connection manager, responsible for handling client connections and broadcasting messages."""
    
    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and save WebSocket connection.
        
        Args:
            websocket: WebSocket connection object.
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Disconnect WebSocket connection.
        
        Args:
            websocket: WebSocket connection object.
        """
        self.active_connections.remove(websocket)

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


# Create connection manager instance
manager = ConnectionManager()