import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.connection_manager import connection_manager
from app.models.user import User
from app.repos import meeting_repo
from app.schemas.ws import (
    WsMessageType,
    WsMessage,
    make_chat_message,
    make_participant_joined,
    make_participant_left,
    make_participant_status,
    make_signaling_forward,
    make_translation_result,
)
from app.schemas.translation import TranslationTask
from app.translation import translation_manager

logger = logging.getLogger("uvicorn.error")


async def on_connect(meeting_code: str, user: User) -> None:
    """Handle a new user connecting to a meeting WebSocket."""
    msg = make_participant_joined(user.id, user.name, user.surname, user.avatar_url)
    await connection_manager.broadcast(meeting_code, msg.model_dump(), exclude_user_id=user.id)
    logger.info(f"[WS] User {user.id} ({user.name}) joined meeting {meeting_code}")


async def on_disconnect(meeting_code: str, user_id: int) -> None:
    """Handle a user disconnecting from a meeting WebSocket."""
    connection_manager.disconnect(meeting_code, user_id)
    msg = make_participant_left(user_id)
    await connection_manager.broadcast(meeting_code, msg.model_dump())
    logger.info(f"[WS] User {user_id} disconnected from meeting {meeting_code}")


async def handle_message(
    db: AsyncSession,
    meeting_code: str,
    meeting_id: int,
    user: User,
    raw_message: dict,
) -> None:
    """Route an incoming WS message to the appropriate handler."""
    try:
        msg_type = WsMessageType(raw_message.get("type", ""))
    except ValueError:
        logger.warning(f"[WS] Unknown message type: {raw_message.get('type')}")
        return

    payload = raw_message.get("payload", {})

    if msg_type == WsMessageType.CHAT_MESSAGE:
        await _handle_chat(db, meeting_code, meeting_id, user, payload)

    elif msg_type in (WsMessageType.SDP_OFFER, WsMessageType.SDP_ANSWER, WsMessageType.ICE_CANDIDATE):
        await _handle_signaling(meeting_code, user.id, msg_type, payload)

    elif msg_type in (WsMessageType.SDP_DEBUG_OFFER, WsMessageType.SDP_DEBUG_ANSWER, WsMessageType.ICE_DEBUG_CANDIDATE):
        await _handle_debug_signaling(meeting_code, user.id, msg_type, payload)

    elif msg_type == WsMessageType.DEBUG_OVERLAY_TOGGLE:
        await _handle_debug_toggle(meeting_code, user.id, payload)

    elif msg_type == WsMessageType.PARTICIPANT_APPROVED:
        await _handle_participant_approval(db, meeting_code, meeting_id, payload, approved=True)

    elif msg_type == WsMessageType.PARTICIPANT_REJECTED:
        await _handle_participant_approval(db, meeting_code, meeting_id, payload, approved=False)


# ── Private handlers ──────────────────────────────────────────

async def _handle_chat(db: AsyncSession, meeting_code: str, meeting_id: int, user: User, payload: dict) -> None:
    content = payload.get("content", "")
    if not content:
        return
    await meeting_repo.add_message(db, meeting_id, user.id, content)
    msg = make_chat_message(user.id, f"{user.name} {user.surname}", content)
    await connection_manager.broadcast(meeting_code, msg.model_dump(), exclude_user_id=user.id)


async def _handle_signaling(meeting_code: str, sender_id: int, msg_type: WsMessageType, payload: dict) -> None:
    target_user_id = int(payload.get("targetUserId", 0))
    if not target_user_id:
        return
    msg = make_signaling_forward(msg_type, sender_id, payload.get("data"))
    await connection_manager.send_to_user(meeting_code, target_user_id, msg.model_dump())


async def _handle_debug_signaling(meeting_code: str, sender_id: int, msg_type: WsMessageType, payload: dict) -> None:
    msg = WsMessage(type=msg_type, payload=payload, senderId=str(sender_id))
    await connection_manager.broadcast(meeting_code, msg.model_dump(), exclude_user_id=sender_id)


async def _handle_debug_toggle(meeting_code: str, user_id: int, payload: dict) -> None:
    enabled = payload.get("enabled", False)
    logger.info(f"[WS] Debug overlay {'enabled' if enabled else 'disabled'} for user {user_id} in meeting {meeting_code}")

    if enabled:
        service = translation_manager.get(meeting_code)
        if service is None:
            service = await translation_manager.register(meeting_code)

        task = TranslationTask(meeting_code=meeting_code, user_id=str(user_id), frame_data=b"")
        result = await service.process_frame(task)

        if result.text:
            msg = make_translation_result(user_id, result.text, result.gesture_label, result.confidence)
            await connection_manager.broadcast(meeting_code, msg.model_dump())


async def _handle_participant_approval(
    db: AsyncSession, meeting_code: str, meeting_id: int, payload: dict, approved: bool
) -> None:
    target_user_id = int(payload.get("userId", 0))
    if not target_user_id:
        return

    status = "approved" if approved else "rejected"
    msg_type = WsMessageType.PARTICIPANT_APPROVED if approved else WsMessageType.PARTICIPANT_REJECTED

    await meeting_repo.update_participant_status(db, meeting_id, target_user_id, status)
    msg = make_participant_status(msg_type, target_user_id)
    await connection_manager.send_to_user(meeting_code, target_user_id, msg.model_dump())
