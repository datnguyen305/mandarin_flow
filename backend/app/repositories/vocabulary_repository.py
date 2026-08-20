import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import SavedVocabulary, Subtitle, Video


class VocabularyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save(
        self,
        guest_id: uuid.UUID,
        word: str,
        pinyin: str | None,
        meaning: str | None,
        video_id: int,
        subtitle_id: int,
        timestamp: float,
    ) -> SavedVocabulary:
        item = SavedVocabulary(
            guest_id=guest_id,
            word=word,
            pinyin=pinyin,
            meaning=meaning,
            video_id=video_id,
            subtitle_id=subtitle_id,
            timestamp=timestamp,
        )
        self.db.add(item)
        await self.db.flush()
        return item

    async def list_for_guest(self, guest_id: uuid.UUID) -> list[SavedVocabulary]:
        result = await self.db.execute(
            select(SavedVocabulary)
            .options(joinedload(SavedVocabulary.video), joinedload(SavedVocabulary.subtitle))
            .where(SavedVocabulary.guest_id == guest_id)
            .order_by(SavedVocabulary.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_for_guest(self, vocabulary_id: int, guest_id: uuid.UUID) -> bool:
        item = await self.db.get(SavedVocabulary, vocabulary_id)
        if item is None or item.guest_id != guest_id:
            return False
        await self.db.delete(item)
        return True

    async def find_video_and_subtitle(self, youtube_video_id: str, subtitle_id: int) -> tuple[Video | None, Subtitle | None]:
        video_result = await self.db.execute(select(Video).where(Video.youtube_video_id == youtube_video_id))
        subtitle_result = await self.db.execute(select(Subtitle).where(Subtitle.id == subtitle_id))
        return video_result.scalar_one_or_none(), subtitle_result.scalar_one_or_none()
