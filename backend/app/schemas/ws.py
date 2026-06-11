from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class WsMessageType(str, Enum):
    CHAT_MESSAGE = "chat_message"
    SDP_OFFER = "sdp_offer"
    SDP_ANSWER = "sdp_answer"
    ICE_CANDIDATE = "ice_candidate"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    PARTICIPANT_APPROVED = "participant_approved"
    PARTICIPANT_REJECTED = "participant_rejected"
    SDP_DEBUG_OFFER = "sdp_debug_offer"
    SDP_DEBUG_ANSWER = "sdp_debug_answer"
    ICE_DEBUG_CANDIDATE = "ice_debug_candidate"
    DEBUG_OVERLAY_TOGGLE = "debug_overlay_toggle"
    VIDEO_FRAME = "video_frame"
    TRANSLATION_RESULT = "translation_result"
    PULSE_SAMPLES = "pulse_samples"
    PULSE_RESULT = "pulse_result"


# ── Base message ──────────────────────────────────────────────

class WsMessage(BaseModel):
    type: WsMessageType
    payload: dict = Field(default_factory=dict)
    senderId: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ── Payloads ──────────────────────────────────────────────────

class ChatPayload(BaseModel):
    content: str
    senderName: str
    senderId: str | None = None


class SignalingPayload(BaseModel):
    targetUserId: str | None = None
    senderId: str | None = None
    data: dict | None = None


class ParticipantPayload(BaseModel):
    userId: str
    firstName: str | None = None
    lastName: str | None = None
    avatarUrl: str | None = None
    status: str | None = None


class DebugTogglePayload(BaseModel):
    enabled: bool = False


class VideoFramePayload(BaseModel):
    frameB64: str
    ts: float = 0.0


class TranslationResultPayload(BaseModel):
    userId: str
    text: str | None = None
    gestureLabel: str | None = None
    confidence: float = 0.0


class PulseSamplesPayload(BaseModel):
    # Each sample is [ts_seconds, mean_r, mean_g, mean_b] for the face ROI.
    samples: list[list[float]] = Field(default_factory=list)


class PulseResultPayload(BaseModel):
    userId: str
    bpm: float | None = None
    confidence: float = 0.0


# ── Factory helpers ───────────────────────────────────────────

def make_chat_message(sender_id: int, sender_name: str, content: str) -> WsMessage:
    return WsMessage(
        type=WsMessageType.CHAT_MESSAGE,
        payload=ChatPayload(content=content, senderName=sender_name, senderId=str(sender_id)).model_dump(),
        senderId=str(sender_id),
    )


def make_participant_joined(user_id: int, first_name: str, last_name: str, avatar_url: str | None = None, status: str | None = None) -> WsMessage:
    return WsMessage(
        type=WsMessageType.PARTICIPANT_JOINED,
        payload=ParticipantPayload(userId=str(user_id), firstName=first_name, lastName=last_name, avatarUrl=avatar_url, status=status).model_dump(),
        senderId=str(user_id),
    )


def make_participant_left(user_id: int) -> WsMessage:
    return WsMessage(
        type=WsMessageType.PARTICIPANT_LEFT,
        payload=ParticipantPayload(userId=str(user_id)).model_dump(),
        senderId=str(user_id),
    )


def make_participant_status(msg_type: WsMessageType, user_id: int) -> WsMessage:
    return WsMessage(
        type=msg_type,
        payload=ParticipantPayload(userId=str(user_id)).model_dump(),
    )


def make_signaling_forward(msg_type: WsMessageType, sender_id: int, data: dict | None) -> WsMessage:
    return WsMessage(
        type=msg_type,
        payload=SignalingPayload(senderId=str(sender_id), data=data).model_dump(),
        senderId=str(sender_id),
    )


def make_translation_result(user_id: int, text: str | None, gesture_label: str | None, confidence: float) -> WsMessage:
    return WsMessage(
        type=WsMessageType.TRANSLATION_RESULT,
        payload=TranslationResultPayload(userId=str(user_id), text=text, gestureLabel=gesture_label, confidence=confidence).model_dump(),
    )


def make_pulse_result(user_id: int, bpm: float | None, confidence: float) -> WsMessage:
    return WsMessage(
        type=WsMessageType.PULSE_RESULT,
        payload=PulseResultPayload(userId=str(user_id), bpm=bpm, confidence=confidence).model_dump(),
    )
