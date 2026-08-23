import pytest
from pydantic import ValidationError

from app.schemas.video import ProcessVideoRequest


def test_process_video_normalizes_and_deduplicates_tags() -> None:
    payload = ProcessVideoRequest(
        url="https://www.youtube.com/watch?v=abc123abc12",
        tags=[" Du lịch ", "du lịch", "Hội   thoại", ""],
    )

    assert payload.tags == ["Du lịch", "Hội thoại"]


def test_process_video_limits_tag_count() -> None:
    payload = ProcessVideoRequest(
        url="https://www.youtube.com/watch?v=abc123abc12",
        tags=[f"Tag {index}" for index in range(12)],
    )

    assert len(payload.tags) == 10


def test_process_video_rejects_url_as_topic() -> None:
    with pytest.raises(ValidationError, match="Video topics cannot be URLs"):
        ProcessVideoRequest(
            url="https://www.youtube.com/watch?v=abc123abc12",
            tags=["https://www.youtube.com/watch?v=abc123abc12"],
        )
