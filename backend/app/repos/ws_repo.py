import asyncio
import base64
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

# How often (seconds) to poke each session so pause-based LLM flush fires
# even after the frame stream stops.
_TICK_INTERVAL_S = 0.4

# Per-(meeting, user) translation state.
#   _session_locks — serialize frame processing vs. the ticker (the ml
#                     session is stateful and not concurrency-safe).
#   _tickers        — background pause-flush tasks.
_session_locks: dict[tuple[str, int], asyncio.Lock] = {}
_tickers: dict[tuple[str, int], asyncio.Task] = {}


async def on_connect(meeting_code: str, user: User, status: str | None = None) -> None:
    """Handle a new user connecting to a meeting WebSocket.

    ``status`` is the connecting user's participant status (e.g. "waiting")
    so the host's client can show them in the approval panel."""
    msg = make_participant_joined(user.id, user.name, user.surname, user.avatar_url, status)
    await connection_manager.broadcast(meeting_code, msg.model_dump(), exclude_user_id=user.id)
    logger.info(f"[WS] User {user.id} ({user.name}) joined meeting {meeting_code} (status={status})")


async def on_disconnect(meeting_code: str, user_id: int) -> None:
    """Handle a user disconnecting from a meeting WebSocket."""
    connection_manager.disconnect(meeting_code, user_id)

    # Tear down this user's translation session + ticker.
    key = (meeting_code, user_id)
    ticker = _tickers.pop(key, None)
    if ticker is not None:
        ticker.cancel()
    _session_locks.pop(key, None)
    await translation_manager.unregister(meeting_code, user_id)
    if not connection_manager.get_user_ids(meeting_code):
        await translation_manager.unregister_meeting(meeting_code)

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

    elif msg_type == WsMessageType.VIDEO_FRAME:
        await _handle_video_frame(meeting_code, user, payload)

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


# ── Sign-language translation ─────────────────────────────────

async def _broadcast_translation(meeting_code: str, user_id: int, result) -> None:
    """Broadcast a translation_result to everyone in the meeting (no exclude —
    the signer sees their own caption too)."""
    if result is None or not result.text:
        return
    msg = make_translation_result(user_id, result.text, result.gesture_label, result.confidence)
    await connection_manager.broadcast(meeting_code, msg.model_dump())


async def _handle_video_frame(meeting_code: str, user: User, payload: dict) -> None:
    """Decode a frame, run it through the user's translation session, and
    broadcast any resulting sentence."""
    frame_b64 = payload.get("frameB64")
    if not frame_b64:
        return
    try:
        frame_data = base64.b64decode(frame_b64)
    except (ValueError, TypeError):
        return

    key = (meeting_code, user.id)
    lock = _session_locks.setdefault(key, asyncio.Lock())
    # Throttle: drop this frame if the previous one (or a tick) is still in
    # flight — MediaPipe + the classifier can't keep up with every frame.
    if lock.locked():
        return

    async with lock:
        service = await translation_manager.get_or_register(meeting_code, user.id)
        _ensure_ticker(meeting_code, user.id)
        task = TranslationTask(meeting_code=meeting_code, user_id=str(user.id), frame_data=frame_data)
        result = await service.process_frame(task)
    await _broadcast_translation(meeting_code, user.id, result)


def _ensure_ticker(meeting_code: str, user_id: int) -> None:
    """Start the per-session pause-flush ticker once."""
    key = (meeting_code, user_id)
    if key in _tickers and not _tickers[key].done():
        return
    _tickers[key] = asyncio.create_task(_ticker_loop(meeting_code, user_id))


async def _ticker_loop(meeting_code: str, user_id: int) -> None:
    """Periodically poke the session so a buffered phrase flushes after a pause
    even when no new frames arrive."""
    while True:
        await asyncio.sleep(_TICK_INTERVAL_S)
        service = translation_manager.get(meeting_code, user_id)
        if service is None:
            return
        lock = _session_locks.get((meeting_code, user_id))
        if lock is None or lock.locked():
            continue
        async with lock:
            task = TranslationTask(meeting_code=meeting_code, user_id=str(user_id), frame_data=b"")
            result = await service.tick(task)
        await _broadcast_translation(meeting_code, user_id, result)


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
