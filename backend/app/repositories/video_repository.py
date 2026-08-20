from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Subtitle, Video


class VideoRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_youtube_id(self, youtube_video_id: str) -> Video | None:
        result = await self.db.execute(select(Video).where(Video.youtube_video_id == youtube_video_id))
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 50, processing_status: str | None = None) -> list[Video]:
        statement = select(Video).order_by(Video.created_at.desc(), Video.id.desc()).limit(limit)
        if processing_status is not None:
            statement = statement.where(Video.processing_status == processing_status)
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def get_with_subtitles(self, youtube_video_id: str) -> Video | None:
        result = await self.db.execute(
            select(Video)
            .options(selectinload(Video.subtitles).selectinload(Subtitle.tokens))
            .where(Video.youtube_video_id == youtube_video_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, youtube_video_id: str, title: str, url: str, thumbnail_url: str | None, language: str) -> Video:
        video = await self.get_by_youtube_id(youtube_video_id)
        if video is None:
            video = Video(
                youtube_video_id=youtube_video_id,
                title=title,
                url=url,
                thumbnail_url=thumbnail_url,
                language=language,
            )
            self.db.add(video)
            try:
                await self.db.flush()
            except IntegrityError:
                await self.db.rollback()
                video = await self.get_by_youtube_id(youtube_video_id)
                if video is None:
                    raise
                video.title = title
                video.url = url
                video.thumbnail_url = thumbnail_url
                video.language = language
                await self.db.flush()
        else:
            video.title = title
            video.url = url
            video.thumbnail_url = thumbnail_url
            video.language = language
            await self.db.flush()
        return video

    async def delete(self, video: Video) -> None:
        await self.db.delete(video)
        await self.db.flush()

    async def set_processing_status(self, video: Video, status: str) -> None:
        video.processing_status = status
        await self.db.flush()

    async def set_processing_status_by_id(self, video_id: int, status: str) -> None:
        await self.db.execute(update(Video).where(Video.id == video_id).values(processing_status=status))
        await self.db.flush()
