from datetime import datetime
import enum

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ParticipantStatus(enum.Enum):
    waiting = "waiting"
    approved = "approved"
    rejected = "rejected"


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meeting_id: Mapped[int] = mapped_column(Integer, ForeignKey("meetings.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    status: Mapped[ParticipantStatus] = mapped_column(Enum(ParticipantStatus), default=ParticipantStatus.waiting)  # waiting, approved, rejected
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship(lazy="joined")
