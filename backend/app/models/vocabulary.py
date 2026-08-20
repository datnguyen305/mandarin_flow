from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SavedVocabulary(Base):
    __tablename__ = "saved_vocabulary"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    word: Mapped[str] = mapped_column(String(128))
    pinyin: Mapped[str | None] = mapped_column(String(256), nullable=True)
    meaning: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    subtitle_id: Mapped[int] = mapped_column(ForeignKey("subtitles.id", ondelete="CASCADE"))
    timestamp: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video")
    subtitle = relationship("Subtitle")
