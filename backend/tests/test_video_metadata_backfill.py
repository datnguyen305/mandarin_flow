from datetime import date, datetime, timezone

import pytest

from app.services import video_metadata_backfill
from app.services.video_metadata_backfill import _apply_metadata, backfill_missing_video_metadata
from app.services.youtube_service import YouTubeMetadata


class FakeVideo:
    id = 1
    youtube_video_id = "abc123abc12"
    url = "https://www.youtube.com/watch?v=abc123abc12"
    title = "Old title"
    thumbnail_url = None
    duration_seconds = None
    channel_name = None
    channel_id = None
    view_count = None
    upload_date = None
    metadata_fetched_at = None


def test_apply_metadata_updates_legacy_video_fields() -> None:
    video = FakeVideo()
    fetched_at = datetime.now(timezone.utc)
    metadata = YouTubeMetadata(
        video_id=video.youtube_video_id,
        title="New title",
        url=video.url,
        thumbnail_url="https://example.com/thumbnail.jpg",
        duration_seconds=120,
        channel_name="Channel",
        channel_id="UC123",
        view_count=1234,
        upload_date=date(2026, 8, 24),
        metadata_fetched_at=fetched_at,
    )

    _apply_metadata(video, metadata)  # type: ignore[arg-type]

    assert video.title == "New title"
    assert video.view_count == 1234
    assert video.channel_name == "Channel"
    assert video.duration_seconds == 120
    assert video.metadata_fetched_at == fetched_at


@pytest.mark.asyncio
async def test_backfill_updates_missing_view_count(monkeypatch) -> None:
    video = FakeVideo()

    class FakeDb:
        async def commit(self) -> None:
            return None

    class FakeSession:
        async def __aenter__(self):
            return FakeDb()

        async def __aexit__(self, *_args):
            return None

    class FakeRepo:
        def __init__(self, _db) -> None:
            pass

        async def list_missing_view_count(self, _limit):
            return [video]

        async def get_by_youtube_id(self, _youtube_id):
            return video

    class FakeYouTubeService:
        async def get_metadata(self, url):
            return YouTubeMetadata(
                video_id=video.youtube_video_id,
                title="Updated",
                url=url,
                thumbnail_url="https://example.com/thumbnail.jpg",
                view_count=9876,
            )

    monkeypatch.setattr(video_metadata_backfill, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(video_metadata_backfill, "VideoRepository", FakeRepo)
    monkeypatch.setattr(video_metadata_backfill, "YouTubeService", FakeYouTubeService)

    result = await backfill_missing_video_metadata()

    assert result.selected == 1
    assert result.updated == 1
    assert result.failed == 0
    assert video.view_count == 9876
