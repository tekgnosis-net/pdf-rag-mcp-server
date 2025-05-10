"""WebSocket管理模块。

该模块提供WebSocket连接管理，用于向客户端推送实时状态更新。
"""

# 标准库导入
from typing import Any, Dict, List

# 第三方库导入
from fastapi import WebSocket


class ConnectionManager:
    """WebSocket连接管理器，负责处理客户端连接和消息广播。"""
    
    def __init__(self):
        """初始化连接管理器。"""
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """接受WebSocket连接并保存。
        
        Args:
            websocket: WebSocket连接对象。
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接。
        
        Args:
            websocket: WebSocket连接对象。
        """
        self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """向所有活跃连接广播消息。
        
        Args:
            message: 要广播的消息。
        """
        for connection in self.active_connections:
            await connection.send_json(message)
            
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """向特定连接发送个人消息。
        
        Args:
            message: 要发送的消息。
            websocket: 接收消息的WebSocket连接。
        """
        await websocket.send_json(message)


# 创建连接管理器实例
manager = ConnectionManager()