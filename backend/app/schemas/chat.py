from datetime import datetime

from pydantic import BaseModel, Field


class ChatMessageResponse(BaseModel):
    id: str = Field(examples=["1"])
    meetingCode: str = Field(examples=["abc12345"])
    senderId: str = Field(examples=["1"])
    senderName: str = Field(examples=["John Smith"])
    content: str = Field(examples=["Hello!"])
    timestamp: str = Field(examples=["2025-01-01T00:00:00"])

    @classmethod
    def from_db(cls, msg, meeting_code: str) -> "ChatMessageResponse":
        sender_name = "Unknown"
        if msg.sender:
            sender_name = f"{msg.sender.name} {msg.sender.surname}"
        return cls(
            id=str(msg.id),
            meetingCode=meeting_code,
            senderId=str(msg.sender_id),
            senderName=sender_name,
            content=msg.content,
            timestamp=msg.created_at.isoformat() if isinstance(msg.created_at, datetime) else str(msg.created_at or ""),
        )
