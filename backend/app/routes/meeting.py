from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection_manager import connection_manager
from app.database import get_db
from app.models.participant import ParticipantStatus
from app.models.user import User
from app.repos import meeting_repo, ws_repo
from app.schemas.meeting import (
    CreateMeetingRequest,
    CreateMeetingResponse,
    MeetingResponse,
)
from app.schemas.chat import ChatMessageResponse
from app.schemas.ws import WsMessageType, make_participant_status
from app.utils.auth.jwt import get_current_user

router = APIRouter(prefix="/meetings", tags=["Meetings"])


@router.post("",
             response_model=CreateMeetingResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Create a new meeting",
             response_description="Meeting data with code")
async def create_meeting(
    data: CreateMeetingRequest = CreateMeetingRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new meeting. \\
    The current user becomes the host.
    """
    meeting = await meeting_repo.create_meeting(db, current_user.id, data.title)
    resp = MeetingResponse.from_db(meeting)
    return CreateMeetingResponse(meeting=resp, code=meeting.code)


@router.get("/{code}",
            response_model=MeetingResponse,
            status_code=status.HTTP_200_OK,
            summary="Get meeting by code",
            response_description="Meeting data with participants")
async def get_meeting(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get meeting details by code. \\
    Includes participant list.
    """
    meeting = await meeting_repo.get_meeting_by_code(db, code)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spotkanie nie znalezione")
    return MeetingResponse.from_db(meeting)


@router.post("/{code}/join",
             status_code=status.HTTP_200_OK,
             summary="Join a meeting",
             response_description="Join status")
async def join_meeting(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Join a meeting. \\
    User is added to the waiting room (status: waiting). \\
    Host must approve participants.
    """
    meeting = await meeting_repo.get_meeting_by_code(db, code)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spotkanie nie znalezione")
    if not meeting.is_active:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Spotkanie zostało zakończone")

    # Host auto-approved
    is_host = meeting.host_id == current_user.id
    participant_status = ParticipantStatus.approved if is_host else ParticipantStatus.waiting

    await meeting_repo.add_participant(db, meeting.id, current_user.id, participant_status, is_host)
    return {"status": participant_status}


@router.post("/{code}/participants/{user_id}/approve",
             status_code=status.HTTP_200_OK,
             summary="Approve a participant",
             response_description="Approval confirmation")
async def approve_participant(
    code: str,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a waiting participant. \\
    Only the meeting host can approve.
    """
    meeting = await meeting_repo.get_meeting_by_code(db, code)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spotkanie nie znalezione")
    if meeting.host_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tylko host może zatwierdzać uczestników")

    participant = await meeting_repo.update_participant_status(db, meeting.id, user_id, ParticipantStatus.approved)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uczestnik nie znaleziony")
    # Notify the guest over WS so their client leaves the waiting screen.
    msg = make_participant_status(WsMessageType.PARTICIPANT_APPROVED, user_id)
    await connection_manager.send_to_user(code, user_id, msg.model_dump())
    # Tell the others — peers start WebRTC towards the guest only now.
    await ws_repo.announce_approved_participant(db, code, user_id)
    return {"status": "approved"}


@router.post("/{code}/participants/{user_id}/reject",
             status_code=status.HTTP_200_OK,
             summary="Reject a participant",
             response_description="Rejection confirmation")
async def reject_participant(
    code: str,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a waiting participant. \\
    Only the meeting host can reject.
    """
    meeting = await meeting_repo.get_meeting_by_code(db, code)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spotkanie nie znalezione")
    if meeting.host_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tylko host może odrzucać uczestników")

    participant = await meeting_repo.update_participant_status(db, meeting.id, user_id, ParticipantStatus.rejected)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uczestnik nie znaleziony")
    # Notify the guest over WS so their client leaves the waiting screen.
    msg = make_participant_status(WsMessageType.PARTICIPANT_REJECTED, user_id)
    await connection_manager.send_to_user(code, user_id, msg.model_dump())
    return {"status": "rejected"}


@router.delete("/{code}/leave",
               status_code=status.HTTP_200_OK,
               summary="Leave a meeting",
               response_description="Leave confirmation")
async def leave_meeting(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Leave a meeting. \\
    Removes the user from participants. \\
    If user is host, the meeting is marked as inactive.
    """
    meeting = await meeting_repo.get_meeting_by_code(db, code)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spotkanie nie znalezione")

    await meeting_repo.remove_participant(db, meeting.id, current_user.id)

    if meeting.host_id == current_user.id:
        await meeting_repo.set_meeting_inactive(db, meeting.id)

    return {"status": "left"}


@router.get("/{code}/messages",
            response_model=list[ChatMessageResponse],
            status_code=status.HTTP_200_OK,
            summary="Get chat message history",
            response_description="List of chat messages")
async def get_messages(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the chat message history for a meeting.
    """
    meeting = await meeting_repo.get_meeting_by_code(db, code)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spotkanie nie znalezione")

    messages = await meeting_repo.get_messages(db, meeting.id)
    return [ChatMessageResponse.from_db(msg, code) for msg in messages]
