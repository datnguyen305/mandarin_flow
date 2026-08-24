import asyncio
import logging
from dataclasses import dataclass

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models import Video
from app.repositories.video_repository import VideoRepository
from app.services.youtube_service import YouTubeMetadata, YouTubeService

logger = logging.getLogger(__name__)

_backfill_lock = asyncio.Lock()


@dataclass(frozen=True)
class MetadataBackfillResult:
    selected: int
    updated: int
    failed: int
    already_running: bool = False


async def backfill_missing_video_metadata() -> MetadataBackfillResult:
    """Refresh metadata for legacy videos without reprocessing their content."""
    if _backfill_lock.locked():
        return MetadataBackfillResult(selected=0, updated=0, failed=0, already_running=True)

    async with _backfill_lock:
        limit = max(1, settings.youtube_metadata_backfill_batch_size)
        async with AsyncSessionLocal() as db:
            videos = await VideoRepository(db).list_missing_view_count(limit)
            candidates = [(video.id, video.youtube_video_id, video.url) for video in videos]

        if not candidates:
            return MetadataBackfillResult(selected=0, updated=0, failed=0)

        semaphore = asyncio.Semaphore(max(1, settings.youtube_metadata_backfill_concurrency))
        results = await asyncio.gather(
            *(_refresh_video_metadata(video_id, youtube_id, url, semaphore) for video_id, youtube_id, url in candidates)
        )
        updated = sum(results)
        result = MetadataBackfillResult(selected=len(candidates), updated=updated, failed=len(candidates) - updated)
        logger.info(
            "YouTube metadata backfill completed selected=%d updated=%d failed=%d",
            result.selected,
            result.updated,
            result.failed,
        )
        return result


async def _refresh_video_metadata(video_id: int, youtube_id: str, url: str, semaphore: asyncio.Semaphore) -> bool:
    try:
        async with semaphore:
            metadata = await YouTubeService().get_metadata(url)
        if metadata.view_count is None:
            logger.warning("YouTube metadata backfill returned no view count youtube_id=%s", youtube_id)
            return False

        async with AsyncSessionLocal() as db:
            video = await VideoRepository(db).get_by_youtube_id(youtube_id)
            if video is None or video.id != video_id:
                return False
            _apply_metadata(video, metadata)
            await db.commit()
        return True
    except Exception as exc:
        logger.warning(
            "YouTube metadata backfill failed youtube_id=%s error_type=%s",
            youtube_id,
            type(exc).__name__,
        )
        return False


def _apply_metadata(video: Video, metadata: YouTubeMetadata) -> None:
    video.title = metadata.title
    video.url = metadata.url
    video.thumbnail_url = metadata.thumbnail_url
    video.view_count = metadata.view_count
    if metadata.duration_seconds is not None:
        video.duration_seconds = metadata.duration_seconds
    if metadata.channel_name is not None:
        video.channel_name = metadata.channel_name
    if metadata.channel_id is not None:
        video.channel_id = metadata.channel_id
    if metadata.upload_date is not None:
        video.upload_date = metadata.upload_date
    if metadata.metadata_fetched_at is not None:
        video.metadata_fetched_at = metadata.metadata_fetched_at
