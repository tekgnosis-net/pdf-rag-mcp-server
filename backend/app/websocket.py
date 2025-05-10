from fastapi import WebSocket, WebSocketDisconnect  
from typing import Dict, List, Any  

class ConnectionManager:  
    def __init__(self):  
        self.active_connections: List[WebSocket] = []  

    async def connect(self, websocket: WebSocket):  
        await websocket.accept()  
        self.active_connections.append(websocket)  

    def disconnect(self, websocket: WebSocket):  
        self.active_connections.remove(websocket)  

    async def broadcast(self, message: Dict[str, Any]):  
        for connection in self.active_connections:  
            await connection.send_json(message)  
            
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):  
        await websocket.send_json(message)  

# 创建连接管理器实例  
manager = ConnectionManager()