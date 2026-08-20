from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Subtitle, SubtitleToken


class SubtitleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_video_id(self, video_id: int) -> list[Subtitle]:
        result = await self.db.execute(
            select(Subtitle)
            .options(selectinload(Subtitle.tokens))
            .where(Subtitle.video_id == video_id)
            .order_by(Subtitle.sequence_number)
        )
        return list(result.scalars().all())

    async def list_by_batch(self, video_id: int, batch_index: int) -> list[Subtitle]:
        result = await self.db.execute(
            select(Subtitle)
            .options(selectinload(Subtitle.tokens))
            .where(Subtitle.video_id == video_id, Subtitle.batch_index == batch_index)
            .order_by(Subtitle.sequence_number)
        )
        return list(result.scalars().all())

    async def replace_for_video(self, video_id: int, lines: list[dict]) -> list[Subtitle]:
        await self.db.execute(delete(Subtitle).where(Subtitle.video_id == video_id))
        subtitles: list[Subtitle] = []
        for index, line in enumerate(lines):
            subtitle = Subtitle(
                video_id=video_id,
                start_time=line["start"],
                end_time=line["end"],
                text=line["text"],
                translated_text=line["translation"],
                sequence_number=index,
            )
            subtitle.tokens = [
                SubtitleToken(
                    text=token["text"],
                    pinyin=token.get("pinyin"),
                    meaning=token.get("meaning"),
                    start_index=token["start_index"],
                    end_index=token["end_index"],
                )
                for token in line["tokens"]
            ]
            self.db.add(subtitle)
            subtitles.append(subtitle)
        await self.db.flush()
        return subtitles

    async def replace_raw_for_video(self, video_id: int, lines: list[dict]) -> list[Subtitle]:
        await self.db.execute(delete(Subtitle).where(Subtitle.video_id == video_id))
        subtitles: list[Subtitle] = []
        for index, line in enumerate(lines):
            subtitle = Subtitle(
                video_id=video_id,
                start_time=line["start"],
                end_time=line["end"],
                text=line["text"],
                translated_text=None,
                sequence_number=index,
                batch_index=line.get("batch_index"),
                processing_status="raw",
            )
            self.db.add(subtitle)
            subtitles.append(subtitle)
        await self.db.flush()
        return subtitles

    async def update_processed_batch(self, video_id: int, batch_index: int, lines: list[dict]) -> list[Subtitle]:
        by_sequence = {line["sequence_number"]: line for line in lines}
        subtitles = await self.list_by_batch(video_id, batch_index)
        for subtitle in subtitles:
            line = by_sequence.get(subtitle.sequence_number)
            if line is None:
                continue
            subtitle.translated_text = line["translation"]
            subtitle.processing_status = "processed"
            subtitle.tokens = [
                SubtitleToken(
                    text=token["text"],
                    pinyin=token.get("pinyin"),
                    meaning=token.get("meaning"),
                    start_index=token["start_index"],
                    end_index=token["end_index"],
                )
                for token in line["tokens"]
            ]
        await self.db.flush()
        return subtitles

    async def mark_batch_failed(self, video_id: int, batch_index: int) -> None:
        subtitles = await self.list_by_batch(video_id, batch_index)
        for subtitle in subtitles:
            subtitle.processing_status = "failed"
        await self.db.flush()

    async def get(self, subtitle_id: int) -> Subtitle | None:
        result = await self.db.execute(select(Subtitle).where(Subtitle.id == subtitle_id))
        return result.scalar_one_or_none()
