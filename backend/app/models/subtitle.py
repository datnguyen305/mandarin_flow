from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Subtitle(Base):
    __tablename__ = "subtitles"
    __table_args__ = (UniqueConstraint("video_id", "sequence_number", name="uq_subtitles_video_sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer)
    batch_index: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    processing_status: Mapped[str] = mapped_column(String(32), default="raw")

    video = relationship("Video", back_populates="subtitles")
    tokens = relationship("SubtitleToken", back_populates="subtitle", cascade="all, delete-orphan", lazy="selectin")
