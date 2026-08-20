from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import build_subtitle_service
from app.core.auth import get_or_create_guest, has_dev_access, require_dev_access
from app.core.config import settings
from app.core.errors import SubtitlesUnavailableError
from app.db.redis import RedisCache, get_cache
from app.db.session import AsyncSessionLocal
from app.db.session import get_db
from app.models import GuestSession
from app.schemas.video import CookiesUploadRequest, PlaybackPositionRequest, ProcessVideoRequest, ProcessVideoResponse, VideoProgressResponse, VideoResponse
from app.services.subtitle_queue import format_sse, subtitle_event_broker, subtitle_processing_queue
from app.services.video_service import VideoService
from app.services.video_progress_service import VideoProgressService

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("/process", response_model=ProcessVideoResponse)
async def process_video(
    payload: ProcessVideoRequest,
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
    _: None = Depends(require_dev_access),
) -> ProcessVideoResponse:
    service = build_subtitle_service(db, cache)
    progress = await service.prepare_video(str(payload.url), payload.source_language, payload.target_language)
    if progress.status != "completed":
        await subtitle_processing_queue.enqueue_video(progress.video_id)
    return ProcessVideoResponse(**progress.model_dump())


@router.get("", response_model=list[VideoResponse])
async def list_videos(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    include_unpublished: bool = Depends(has_dev_access),
) -> list[VideoResponse]:
    videos = await VideoService(db).list_recent(limit, include_unpublished=include_unpublished)
    return [VideoResponse.model_validate(video) for video in videos]


@router.get("/progress", response_model=list[VideoProgressResponse])
async def list_video_progress(
    db: AsyncSession = Depends(get_db),
    guest: GuestSession = Depends(get_or_create_guest),
) -> list[VideoProgressResponse]:
    return await VideoProgressService(db).list_for_guest(guest.id)


@router.post("/cookies", status_code=status.HTTP_202_ACCEPTED)
async def upload_youtube_cookies(payload: CookiesUploadRequest, _: None = Depends(require_dev_access)) -> dict[str, str]:
    content = payload.content.strip()
    if not content:
        raise SubtitlesUnavailableError("Cookies content is empty.")

    cookies_path = Path(settings.yt_dlp_cookies_file or "/app/cookies/cookies.txt")
    cookies_path.parent.mkdir(parents=True, exist_ok=True)
    cookies_path.write_text(content + "\n", encoding="utf-8")
    return {"status": "saved", "path": str(cookies_path)}


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: str, db: AsyncSession = Depends(get_db)) -> VideoResponse:
    video = await VideoService(db).get_by_youtube_id(video_id)
    return VideoResponse.model_validate(video)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
    _: None = Depends(require_dev_access),
) -> None:
    await VideoService(db, cache).delete_by_youtube_id(video_id)


@router.get("/{video_id}/subtitles/raw")
async def get_video_raw_subtitles(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
):
    service = build_subtitle_service(db, cache)
    return await service.get_raw_subtitles(video_id)


@router.get("/{video_id}/subtitles")
async def get_video_subtitles(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
):
    service = build_subtitle_service(db, cache)
    return await service.get_subtitles(video_id)


@router.get("/{video_id}/subtitles/stream")
async def stream_video_subtitles(video_id: str) -> StreamingResponse:
    async def events() -> AsyncGenerator[str, None]:
        async with AsyncSessionLocal() as db:
            service = build_subtitle_service(db, RedisCache(None))
            try:
                progress = await service.progress_for_youtube_id(video_id)
                completed_batches = await service.completed_batch_events(video_id)
            except SubtitlesUnavailableError as exc:
                yield format_sse("processing_failed", {"video_id": video_id, "message": exc.message}, event_id=f"{video_id}:unavailable")
                return

        yield format_sse("processing_progress", progress.model_dump(), event_id=f"{video_id}:progress")
        for batch in completed_batches:
            yield format_sse("subtitle_batch", batch.model_dump(), event_id=f"{video_id}:batch:{batch.batch_index}")
        if progress.status == "completed":
            yield format_sse("processing_completed", {"video_id": video_id}, event_id=f"{video_id}:completed")
            return
        async for message in subtitle_event_broker.subscribe(video_id):
            yield format_sse(message["event"], message["data"])

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/{video_id}/playback-position", status_code=status.HTTP_202_ACCEPTED)
async def update_playback_position(
    video_id: str,
    payload: PlaybackPositionRequest,
    db: AsyncSession = Depends(get_db),
    guest: GuestSession = Depends(get_or_create_guest),
) -> dict[str, str]:
    await VideoProgressService(db).update(guest.id, video_id, payload.current_time)
    await subtitle_processing_queue.prioritize_batch(video_id, payload.current_time)
    return {"status": "accepted"}


@router.post("/{video_id}/batches/{batch_index}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_subtitle_batch(video_id: str, batch_index: int) -> dict[str, str]:
    await subtitle_processing_queue.retry_batch(video_id, batch_index)
    return {"status": "accepted"}
