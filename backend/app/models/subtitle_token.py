from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SubtitleToken(Base):
    __tablename__ = "subtitle_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    subtitle_id: Mapped[int] = mapped_column(ForeignKey("subtitles.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(128))
    pinyin: Mapped[str | None] = mapped_column(String(256), nullable=True)
    meaning: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_index: Mapped[int] = mapped_column(Integer)
    end_index: Mapped[int] = mapped_column(Integer)

    subtitle = relationship("Subtitle", back_populates="tokens")
