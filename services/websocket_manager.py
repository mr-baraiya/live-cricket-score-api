import asyncio
import logging
from typing import Dict, List, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("cricket.websocket_manager")


class WebSocketManager:
    def __init__(self):
        # Match ID -> List of WebSocket connections
        self._active_connections: Dict[str, List[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, match_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            if match_id not in self._active_connections:
                self._active_connections[match_id] = []
            self._active_connections[match_id].append(websocket)
        logger.info("WebSocket connected for match %s (total clients for match: %d)",
                    match_id, len(self._active_connections[match_id]))

    async def disconnect(self, match_id: str, websocket: WebSocket):
        async with self._lock:
            if match_id in self._active_connections:
                if websocket in self._active_connections[match_id]:
                    self._active_connections[match_id].remove(websocket)
                if not self._active_connections[match_id]:
                    del self._active_connections[match_id]
        logger.info("WebSocket disconnected for match %s", match_id)

    async def broadcast_to_match(self, match_id: str, message: dict):
        async with self._lock:
            connections = list(self._active_connections.get(match_id, []))

        if not connections:
            return

        disconnected: List[WebSocket] = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError, Exception) as exc:
                logger.warning("Failed to send WS message to client for match %s: %s", match_id, exc)
                disconnected.append(connection)

        if disconnected:
            async with self._lock:
                if match_id in self._active_connections:
                    for conn in disconnected:
                        if conn in self._active_connections[match_id]:
                            self._active_connections[match_id].remove(conn)
                    if not self._active_connections[match_id]:
                        del self._active_connections[match_id]

    def get_active_client_count(self, match_id: Optional[str] = None) -> int:
        if match_id:
            return len(self._active_connections.get(match_id, []))
        return sum(len(conns) for conns in self._active_connections.values())


websocket_manager = WebSocketManager()
