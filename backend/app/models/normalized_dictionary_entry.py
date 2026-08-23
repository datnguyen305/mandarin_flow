from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NormalizedDictionaryEntry(Base):
    __tablename__ = "normalized_dictionary_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    simplified: Mapped[str] = mapped_column(String(128), index=True)
    traditional: Mapped[str] = mapped_column(String(128), index=True)
    entry_type: Mapped[str] = mapped_column(String(32), index=True)
    readings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    references_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    hsk_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, index=True)
    source_name: Mapped[str] = mapped_column(String(32), default="cvdict")
    source_raw_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    normalized_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), index=True)
    validation_issues: Mapped[list[str]] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
