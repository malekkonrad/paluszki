from datetime import datetime

from pydantic import BaseModel, Field


class CreateMeetingRequest(BaseModel):
    title: str | None = Field(default=None, examples=["Team Standup"])


class ParticipantResponse(BaseModel):
    userId: str = Field(examples=["1"])
    firstName: str = Field(examples=["John"])
    lastName: str = Field(examples=["Smith"])
    avatarUrl: str | None = Field(default=None)
    status: str = Field(examples=["approved"])
    joinedAt: str = Field(examples=["2025-01-01T00:00:00"])
    isHost: bool = Field(examples=[False])

    @classmethod
    def from_db(cls, participant) -> "ParticipantResponse":
        return cls(
            userId=str(participant.user_id),
            firstName=participant.user.name if participant.user else "Unknown",
            lastName=participant.user.surname if participant.user else "",
            avatarUrl=participant.user.avatar_url if participant.user else None,
            status=participant.status,
            joinedAt=participant.joined_at.isoformat() if isinstance(participant.joined_at, datetime) else str(participant.joined_at or ""),
            isHost=participant.is_host,
        )


class MeetingResponse(BaseModel):
    id: str = Field(examples=["1"])
    code: str = Field(examples=["abc12345"])
    title: str = Field(examples=["Team Standup"])
    hostId: str = Field(examples=["1"])
    participants: list[ParticipantResponse] = Field(default_factory=list)
    createdAt: str = Field(examples=["2025-01-01T00:00:00"])
    isActive: bool = Field(examples=[True])

    @classmethod
    def from_db(cls, meeting) -> "MeetingResponse":
        return cls(
            id=str(meeting.id),
            code=meeting.code,
            title=meeting.title or "Spotkanie",
            hostId=str(meeting.host_id),
            participants=[ParticipantResponse.from_db(p) for p in (meeting.participants or [])],
            createdAt=meeting.created_at.isoformat() if isinstance(meeting.created_at, datetime) else str(meeting.created_at or ""),
            isActive=meeting.is_active,
        )


class CreateMeetingResponse(BaseModel):
    meeting: MeetingResponse
    code: str
