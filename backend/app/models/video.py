from datetime import date, datetime

from sqlalchemy import BigInteger, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    youtube_video_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000))
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(nullable=True)
    channel_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    view_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    upload_date: Mapped[date | None] = mapped_column(nullable=True)
    metadata_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="zh")
    processing_status: Mapped[str] = mapped_column(String(32), default="pending")
    processing_phase: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")
    processing_progress: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    processing_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subtitles = relationship("Subtitle", back_populates="video", cascade="all, delete-orphan")
