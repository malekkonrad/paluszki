import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection_manager import connection_manager
from app.database import get_db
from app.repos import auth_repo, meeting_repo
from app.repos import ws_repo
from app.utils.auth.jwt import decode_token

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["WebSocket"])


def _authenticate_ws(token: str) -> int | None:
    """Authenticate a WebSocket connection and return user_id."""
    try:
        payload = decode_token(token)
        return int(payload.get("sub", 0)) or None
    except Exception:
        return None


@router.websocket("/ws/meetings/{code}")
async def websocket_meeting(
    websocket: WebSocket,
    code: str,
    token: str = "",
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for meeting real-time communication.

    Handles: chat_message, sdp_offer/answer, ice_candidate,
    participant_joined/left, participant_approved/rejected,
    video_frame, translation_result, pulse_samples, pulse_result.
    """
    user_id = _authenticate_ws(token)
    if user_id is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    user = await auth_repo.get_user_by_id(db, user_id)
    if user is None:
        await websocket.close(code=4001, reason="User not found")
        return

    meeting = await meeting_repo.get_meeting_by_code(db, code)
    if meeting is None:
        await websocket.close(code=4004, reason="Meeting not found")
        return

    # Only participants may attach to the meeting socket. Waiting guests are
    # allowed (they need the approval notification), rejected ones are not.
    participant_status = next(
        (p.status.value for p in (meeting.participants or []) if p.user_id == user_id),
        None,
    )
    if participant_status is None:
        await websocket.close(code=4003, reason="Not a participant")
        return
    if participant_status == "rejected":
        await websocket.close(code=4003, reason="Rejected")
        return

    await websocket.accept()
    await connection_manager.connect(code, user_id, websocket)
    await ws_repo.on_connect(code, user, participant_status)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await ws_repo.handle_message(db, code, meeting.id, user, message)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[WS] Error for user {user_id} in meeting {code}: {e}")
    finally:
        await ws_repo.on_disconnect(code, user_id, websocket)
