import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.repositories.vocabulary_repository import VocabularyRepository
from app.schemas.vocabulary import SavedVocabularyResponse


class VocabularyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = VocabularyRepository(db)

    async def save(
        self,
        guest_id: uuid.UUID,
        word: str,
        pinyin: str | None,
        meaning: str | None,
        youtube_video_id: str,
        subtitle_id: int,
        timestamp: float,
    ) -> int:
        video, subtitle = await self.repo.find_video_and_subtitle(youtube_video_id, subtitle_id)
        if video is None or subtitle is None or subtitle.video_id != video.id:
            raise AppError("Video or subtitle not found")
        item = await self.repo.save(guest_id, word, pinyin, meaning, video.id, subtitle.id, timestamp)
        await self.db.commit()
        return item.id

    async def list_for_guest(self, guest_id: uuid.UUID) -> list[SavedVocabularyResponse]:
        items = await self.repo.list_for_guest(guest_id)
        return [
            SavedVocabularyResponse(
                id=item.id,
                word=item.word,
                pinyin=item.pinyin,
                meaning=item.meaning,
                youtube_video_id=item.video.youtube_video_id,
                video_title=item.video.title,
                subtitle_sentence=item.subtitle.text,
                timestamp=item.timestamp,
                created_at=item.created_at,
            )
            for item in items
        ]

    async def delete_for_guest(self, vocabulary_id: int, guest_id: uuid.UUID) -> bool:
        deleted = await self.repo.delete_for_guest(vocabulary_id, guest_id)
        await self.db.commit()
        return deleted
