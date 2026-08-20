import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import GuestVideoProgress, Video
from app.schemas.video import VideoProgressResponse


class VideoProgressService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def update(self, guest_id: uuid.UUID, youtube_video_id: str, current_time: float) -> None:
        result = await self.db.execute(select(Video).where(Video.youtube_video_id == youtube_video_id))
        video = result.scalar_one_or_none()
        if video is None:
            return
        statement = insert(GuestVideoProgress).values(
            guest_id=guest_id,
            video_id=video.id,
            current_time=max(0, current_time),
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_guest_video_progress_guest_video",
            set_={"current_time": statement.excluded.current_time, "last_watched_at": func.now()},
        )
        await self.db.execute(statement)
        await self.db.commit()

    async def list_for_guest(self, guest_id: uuid.UUID) -> list[VideoProgressResponse]:
        result = await self.db.execute(
            select(GuestVideoProgress)
            .options(joinedload(GuestVideoProgress.video))
            .where(GuestVideoProgress.guest_id == guest_id)
            .order_by(GuestVideoProgress.last_watched_at.desc())
        )
        return [
            VideoProgressResponse(
                youtube_video_id=item.video.youtube_video_id,
                current_time=item.current_time,
                completed=item.completed,
                last_watched_at=item.last_watched_at,
            )
            for item in result.scalars().all()
        ]
