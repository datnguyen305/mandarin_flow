import pytest

from app.services.video_service import VideoService


class FakeVideo:
    youtube_video_id = "abc123abc12"
    title = "Demo video"


class FakeVideoRepository:
    def __init__(self) -> None:
        self.received_limit: int | None = None
        self.deleted_video = None

    async def list_recent(self, limit: int, processing_status: str | None = None):
        self.received_limit = limit
        self.received_processing_status = processing_status
        return [FakeVideo()]

    async def get_by_youtube_id(self, video_id: str):
        return FakeVideo()

    async def delete(self, video):
        self.deleted_video = video


class FakeDb:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class FakeCache:
    def __init__(self) -> None:
        self.deleted_keys: list[str] = []

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)


@pytest.mark.asyncio
async def test_list_recent_imported_videos_clamps_limit() -> None:
    service = VideoService(None)  # type: ignore[arg-type]
    repo = FakeVideoRepository()
    service.repo = repo  # type: ignore[assignment]

    videos = await service.list_recent(500)

    assert repo.received_limit == 100
    assert repo.received_processing_status == "completed"
    assert videos[0].youtube_video_id == "abc123abc12"


@pytest.mark.asyncio
async def test_list_recent_imported_videos_can_include_unpublished_for_dev() -> None:
    service = VideoService(None)  # type: ignore[arg-type]
    repo = FakeVideoRepository()
    service.repo = repo  # type: ignore[assignment]

    await service.list_recent(50, include_unpublished=True)

    assert repo.received_processing_status is None


@pytest.mark.asyncio
async def test_delete_imported_video_removes_db_row_and_cache() -> None:
    db = FakeDb()
    cache = FakeCache()
    service = VideoService(db, cache)  # type: ignore[arg-type]
    repo = FakeVideoRepository()
    service.repo = repo  # type: ignore[assignment]

    await service.delete_by_youtube_id("abc123abc12")

    assert repo.deleted_video is not None
    assert db.committed is True
    assert cache.deleted_keys == ["video:abc123abc12:subtitles:zh-vi"]
