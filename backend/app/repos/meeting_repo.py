import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meeting import Meeting, Participant, ChatMessage


def _generate_code() -> str:
    return secrets.token_urlsafe(6)[:8]


async def create_meeting(db: AsyncSession, host_id: int, title: str | None = None) -> Meeting:
    code = _generate_code()

    # Ensure unique code
    while True:
        stmt = select(Meeting).where(Meeting.code == code)
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            break
        code = _generate_code()

    meeting = Meeting(
        code=code,
        title=title or "Spotkanie",
        host_id=host_id,
        is_active=True,
    )
    db.add(meeting)
    await db.flush()

    # Add host as approved participant
    participant = Participant(
        meeting_id=meeting.id,
        user_id=host_id,
        status="approved",
        is_host=True,
    )
    db.add(participant)
    await db.commit()
    await db.refresh(meeting)

    # Re-fetch with relationships
    return await get_meeting_by_code(db, code)


async def get_meeting_by_code(db: AsyncSession, code: str) -> Meeting | None:
    stmt = (
        select(Meeting)
        .where(Meeting.code == code)
        .options(selectinload(Meeting.participants).selectinload(Participant.user))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_meeting_by_id(db: AsyncSession, meeting_id: int) -> Meeting | None:
    stmt = (
        select(Meeting)
        .where(Meeting.id == meeting_id)
        .options(selectinload(Meeting.participants).selectinload(Participant.user))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def add_participant(
    db: AsyncSession, meeting_id: int, user_id: int, status: str = "waiting", is_host: bool = False
) -> Participant:
    # Check if already a participant
    stmt = select(Participant).where(
        Participant.meeting_id == meeting_id,
        Participant.user_id == user_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.status = status
        await db.commit()
        await db.refresh(existing)
        return existing

    participant = Participant(
        meeting_id=meeting_id,
        user_id=user_id,
        status=status,
        is_host=is_host,
    )
    db.add(participant)
    await db.commit()
    await db.refresh(participant)
    return participant


async def update_participant_status(db: AsyncSession, meeting_id: int, user_id: int, status: str) -> Participant | None:
    stmt = select(Participant).where(
        Participant.meeting_id == meeting_id,
        Participant.user_id == user_id,
    )
    result = await db.execute(stmt)
    participant = result.scalar_one_or_none()
    if participant is None:
        return None

    participant.status = status
    await db.commit()
    await db.refresh(participant)
    return participant


async def remove_participant(db: AsyncSession, meeting_id: int, user_id: int) -> None:
    stmt = select(Participant).where(
        Participant.meeting_id == meeting_id,
        Participant.user_id == user_id,
    )
    result = await db.execute(stmt)
    participant = result.scalar_one_or_none()
    if participant:
        await db.delete(participant)
        await db.commit()


async def set_meeting_inactive(db: AsyncSession, meeting_id: int) -> None:
    stmt = select(Meeting).where(Meeting.id == meeting_id)
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()
    if meeting:
        meeting.is_active = False
        await db.commit()


async def add_message(db: AsyncSession, meeting_id: int, sender_id: int, content: str) -> ChatMessage:
    msg = ChatMessage(
        meeting_id=meeting_id,
        sender_id=sender_id,
        content=content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_messages(db: AsyncSession, meeting_id: int) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.meeting_id == meeting_id)
        .options(selectinload(ChatMessage.sender))
        .order_by(ChatMessage.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
