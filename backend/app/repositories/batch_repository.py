from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SubtitleProcessingBatch


class BatchRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_video(self, video_id: int) -> list[SubtitleProcessingBatch]:
        result = await self.db.execute(
            select(SubtitleProcessingBatch)
            .where(SubtitleProcessingBatch.video_id == video_id)
            .order_by(SubtitleProcessingBatch.batch_index)
        )
        return list(result.scalars().all())

    async def get(self, video_id: int, batch_index: int) -> SubtitleProcessingBatch | None:
        result = await self.db.execute(
            select(SubtitleProcessingBatch).where(
                SubtitleProcessingBatch.video_id == video_id,
                SubtitleProcessingBatch.batch_index == batch_index,
            )
        )
        return result.scalar_one_or_none()

    async def create_missing(self, video_id: int, batches: list[dict]) -> None:
        existing = {batch.batch_index for batch in await self.list_for_video(video_id)}
        for batch in batches:
            if batch["batch_index"] in existing:
                continue
            self.db.add(
                SubtitleProcessingBatch(
                    video_id=video_id,
                    batch_index=batch["batch_index"],
                    start_time=batch["start_time"],
                    end_time=batch["end_time"],
                    status="pending",
                )
            )
        await self.db.flush()

    async def mark_status(self, video_id: int, batch_index: int, status: str) -> None:
        values = {"status": status, "updated_at": func.now()}
        if status == "completed":
            values["processed_at"] = datetime.now(timezone.utc)
        await self.db.execute(
            update(SubtitleProcessingBatch)
            .where(SubtitleProcessingBatch.video_id == video_id, SubtitleProcessingBatch.batch_index == batch_index)
            .values(**values)
        )
        await self.db.flush()
