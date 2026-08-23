"""Bounded backfill for videos missing normalized YouTube metadata."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.video import Video
from app.services.youtube_service import YouTubeService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    service = YouTubeService()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Video)
            .where(
                (Video.duration_seconds.is_(None))
                | (Video.channel_name.is_(None))
                | (Video.channel_id.is_(None))
                | (Video.upload_date.is_(None))
            )
            .order_by(Video.id)
        )
        videos = list(result.scalars().all())
        logger.info("metadata backfill candidates=%d", len(videos))
        for video in videos:
            try:
                metadata = await service.get_metadata(video.url)
                video.title = metadata.title
                video.thumbnail_url = metadata.thumbnail_url
                if metadata.duration_seconds is not None:
                    video.duration_seconds = metadata.duration_seconds
                if metadata.channel_name is not None:
                    video.channel_name = metadata.channel_name
                if metadata.channel_id is not None:
                    video.channel_id = metadata.channel_id
                if metadata.upload_date is not None:
                    video.upload_date = metadata.upload_date
                video.metadata_fetched_at = metadata.metadata_fetched_at
                await db.commit()
                logger.info("metadata backfilled youtube_id=%s source=%s", video.youtube_video_id, metadata.metadata_source)
            except Exception:
                await db.rollback()
                logger.exception("metadata backfill failed youtube_id=%s", video.youtube_video_id)
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
