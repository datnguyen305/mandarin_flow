from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import VideoUnavailableError
from app.db.redis import RedisCache
from app.models import Video
from app.repositories.video_repository import VideoRepository


class VideoService:
    def __init__(self, db: AsyncSession, cache: RedisCache | None = None) -> None:
        self.db = db
        self.cache = cache
        self.repo = VideoRepository(db)

    async def list_recent(self, limit: int = 50, include_unpublished: bool = False) -> list[Video]:
        safe_limit = min(max(limit, 1), 100)
        status = None if include_unpublished else "completed"
        return await self.repo.list_recent(safe_limit, processing_status=status)

    async def get_by_youtube_id(self, video_id: str) -> Video:
        video = await self.repo.get_by_youtube_id(video_id)
        if video is None:
            raise VideoUnavailableError("Video not found")
        return video

    async def delete_by_youtube_id(self, video_id: str) -> None:
        video = await self.get_by_youtube_id(video_id)
        await self.repo.delete(video)
        await self.db.commit()
        if self.cache is not None:
            await self.cache.delete(f"video:{video_id}:subtitles:zh-vi")
