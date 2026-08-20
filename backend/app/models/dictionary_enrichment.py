from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DictionaryEnrichmentCache(Base):
    __tablename__ = "dictionary_enrichment_cache"
    __table_args__ = (
        UniqueConstraint(
            "word",
            "context_hash",
            "source_language",
            "target_language",
            name="uq_dictionary_enrichment_lookup",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(128), index=True)
    context_hash: Mapped[str] = mapped_column(String(64), index=True)
    context: Mapped[str] = mapped_column(String(4000))
    source_language: Mapped[str] = mapped_column(String(16))
    target_language: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(128))
    enrichment_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
