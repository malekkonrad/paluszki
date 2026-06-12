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

    async def connect(self, meeting_code: str, user_id: int, websocket: WebSocket) -> None:
        """Register a user's WebSocket connection for a meeting.

        One live socket per (meeting, user): a second login from the same
        account takes over and the old socket is closed — otherwise the stale
        entry shadows the new one and both sessions misbehave."""
        if meeting_code not in self._connections:
            self._connections[meeting_code] = {}
        old = self._connections[meeting_code].get(user_id)
        self._connections[meeting_code][user_id] = websocket
        if old is not None:
            try:
                await old.close(code=4008, reason="Connected from another session")
            except Exception:
                pass
            logger.info(f"[ConnectionManager] User {user_id} reconnected to meeting {meeting_code}, old socket kicked")
        logger.info(f"[ConnectionManager] User {user_id} connected to meeting {meeting_code}")

    def disconnect(self, meeting_code: str, user_id: int, websocket: WebSocket | None = None) -> None:
        """Remove a user's connection. Cleans up empty meetings.

        When ``websocket`` is given, only remove if it's still the registered
        socket — the teardown of a kicked old connection must not unregister
        the replacement that already took its slot."""
        conns = self._connections.get(meeting_code)
        if conns is None:
            return
        if websocket is not None and conns.get(user_id) is not websocket:
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
