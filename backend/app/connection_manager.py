import logging

from fastapi import WebSocket

logger = logging.getLogger("uvicorn.error")


class ConnectionManager:
    """
    Manages WebSocket connections per meeting.
    Similar pattern to DatabaseSessionManager — one global instance.
    """

    def __init__(self):
        # { meeting_code: { user_id: WebSocket } }
        self._connections: dict[str, dict[int, WebSocket]] = {}

    def connect(self, meeting_code: str, user_id: int, websocket: WebSocket) -> None:
        """Register a user's WebSocket connection for a meeting."""
        if meeting_code not in self._connections:
            self._connections[meeting_code] = {}
        self._connections[meeting_code][user_id] = websocket
        logger.info(f"[ConnectionManager] User {user_id} connected to meeting {meeting_code}")

    def disconnect(self, meeting_code: str, user_id: int) -> None:
        """Remove a user's connection. Cleans up empty meetings."""
        conns = self._connections.get(meeting_code)
        if conns is None:
            return
        conns.pop(user_id, None)
        if not conns:
            self._connections.pop(meeting_code, None)
        logger.info(f"[ConnectionManager] User {user_id} disconnected from meeting {meeting_code}")

    def get_socket(self, meeting_code: str, user_id: int) -> WebSocket | None:
        """Get the WebSocket for a specific user in a meeting."""
        return self._connections.get(meeting_code, {}).get(user_id)

    def get_meeting_sockets(self, meeting_code: str) -> dict[int, WebSocket]:
        """Get all active connections for a meeting."""
        return dict(self._connections.get(meeting_code, {}))

    def get_user_ids(self, meeting_code: str) -> list[int]:
        """Get list of connected user IDs for a meeting."""
        return list(self._connections.get(meeting_code, {}).keys())

    def is_connected(self, meeting_code: str, user_id: int) -> bool:
        """Check if a user is connected to a meeting."""
        return user_id in self._connections.get(meeting_code, {})

    async def send_to_user(self, meeting_code: str, user_id: int, message: dict) -> None:
        """Send a JSON message to a specific user."""
        ws = self.get_socket(meeting_code, user_id)
        if ws is None:
            return
        try:
            await ws.send_json(message)
        except Exception:
            self.disconnect(meeting_code, user_id)

    async def broadcast(self, meeting_code: str, message: dict, exclude_user_id: int | None = None) -> None:
        """Broadcast a JSON message to all users in a meeting."""
        conns = self.get_meeting_sockets(meeting_code)
        disconnected = []
        for uid, ws in conns.items():
            if uid == exclude_user_id:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(uid)
        for uid in disconnected:
            self.disconnect(meeting_code, uid)


# Global singleton — same pattern as sessionmanager
connection_manager = ConnectionManager()
