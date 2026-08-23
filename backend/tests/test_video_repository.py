import pytest

from app.models.video import Video
from app.repositories.video_repository import VideoRepository


class FakeDb:
    async def flush(self) -> None:
        pass


@pytest.mark.asyncio
async def test_set_processing_phase_does_not_move_progress_backwards() -> None:
    video = Video(
        youtube_video_id="abc123abc12",
        title="Demo",
        url="https://youtube.com/watch?v=abc123abc12",
        language="zh",
        processing_phase="segmenting",
        processing_progress=0.72,
    )
    repo = VideoRepository(FakeDb())  # type: ignore[arg-type]

    await repo.set_processing_phase(video, "translating", 0.43)

    assert video.processing_phase == "segmenting"
    assert video.processing_progress == 0.72


@pytest.mark.asyncio
async def test_set_processing_phase_clamps_progress_to_one() -> None:
    video = Video(
        youtube_video_id="abc123abc12",
        title="Demo",
        url="https://youtube.com/watch?v=abc123abc12",
        language="zh",
        processing_progress=0.72,
    )
    repo = VideoRepository(FakeDb())  # type: ignore[arg-type]

    await repo.set_processing_phase(video, "completed", 1.5)

    assert video.processing_progress == 1.0
