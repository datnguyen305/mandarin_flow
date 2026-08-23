from datetime import date, datetime

from sqlalchemy import case, func, select, update
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

    async def upsert(
        self,
        youtube_video_id: str,
        title: str,
        url: str,
        thumbnail_url: str | None,
        language: str,
        tags: list[str] | None = None,
        duration_seconds: int | None = None,
        channel_name: str | None = None,
        channel_id: str | None = None,
        upload_date: date | None = None,
        metadata_fetched_at: datetime | None = None,
    ) -> Video:
        video = await self.get_by_youtube_id(youtube_video_id)
        if video is None:
            video = Video(
                youtube_video_id=youtube_video_id,
                title=title,
                url=url,
                thumbnail_url=thumbnail_url,
                language=language,
                tags=tags or [],
                duration_seconds=duration_seconds,
                channel_name=channel_name,
                channel_id=channel_id,
                upload_date=upload_date,
                metadata_fetched_at=metadata_fetched_at,
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
                if tags is not None:
                    video.tags = tags
                self._merge_metadata(video, duration_seconds, channel_name, channel_id, upload_date, metadata_fetched_at)
                await self.db.flush()
        else:
            video.title = title
            video.url = url
            video.thumbnail_url = thumbnail_url
            video.language = language
            if tags is not None:
                video.tags = tags
            self._merge_metadata(video, duration_seconds, channel_name, channel_id, upload_date, metadata_fetched_at)
            await self.db.flush()
        return video

    @staticmethod
    def _merge_metadata(
        video: Video,
        duration_seconds: int | None,
        channel_name: str | None,
        channel_id: str | None,
        upload_date: date | None,
        metadata_fetched_at: datetime | None,
    ) -> None:
        if duration_seconds is not None:
            video.duration_seconds = duration_seconds
        if channel_name is not None:
            video.channel_name = channel_name
        if channel_id is not None:
            video.channel_id = channel_id
        if upload_date is not None:
            video.upload_date = upload_date
        if metadata_fetched_at is not None:
            video.metadata_fetched_at = metadata_fetched_at

    async def set_tags(self, video: Video, tags: list[str]) -> None:
        video.tags = tags
        await self.db.flush()

    async def delete(self, video: Video) -> None:
        await self.db.delete(video)
        await self.db.flush()

    async def set_processing_status(self, video: Video, status: str) -> None:
        video.processing_status = status
        await self.db.flush()

    async def set_processing_phase(self, video: Video, phase: str, progress: float) -> None:
        current_progress = float(video.processing_progress or 0.0)
        next_progress = max(0.0, min(1.0, progress))
        if next_progress >= current_progress:
            video.processing_phase = phase
        video.processing_progress = max(current_progress, next_progress)
        await self.db.flush()

    async def set_processing_phase_by_youtube_id(self, youtube_video_id: str, phase: str, progress: float) -> None:
        clamped_progress = max(0.0, min(1.0, progress))
        await self.db.execute(
            update(Video)
            .where(Video.youtube_video_id == youtube_video_id)
            .values(
                processing_phase=case(
                    (clamped_progress >= Video.processing_progress, phase),
                    else_=Video.processing_phase,
                ),
                processing_progress=func.greatest(Video.processing_progress, clamped_progress),
            )
        )
        await self.db.flush()

    async def set_processing_status_by_id(self, video_id: int, status: str) -> None:
        await self.db.execute(update(Video).where(Video.id == video_id).values(processing_status=status))
        await self.db.flush()
