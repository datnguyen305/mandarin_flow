import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GuestVideoProgress(Base):
    __tablename__ = "guest_video_progress"
    __table_args__ = (UniqueConstraint("guest_id", "video_id", name="uq_guest_video_progress_guest_video"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    guest_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guest_sessions.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    current_time: Mapped[float] = mapped_column(Float, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_watched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    guest = relationship("GuestSession", back_populates="video_progress")
    video = relationship("Video")
