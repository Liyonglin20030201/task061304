from fastapi import WebSocket
import json


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)

    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections:
            self.active_connections[channel] = [
                c for c in self.active_connections[channel] if c != websocket
            ]

    async def broadcast(self, channel: str, data: dict):
        if channel not in self.active_connections:
            return
        disconnected = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn, channel)

    async def send_personal(self, websocket: WebSocket, data: dict):
        await websocket.send_json(data)


manager = ConnectionManager()
