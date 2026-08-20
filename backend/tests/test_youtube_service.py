import pytest

from app.core.errors import InvalidYouTubeUrlError
from app.services.youtube_service import YouTubeService


def test_extract_video_id_from_watch_url() -> None:
    service = YouTubeService()
    assert service.extract_video_id("https://www.youtube.com/watch?v=abc123abc12") == "abc123abc12"


def test_extract_video_id_from_short_url() -> None:
    service = YouTubeService()
    assert service.extract_video_id("https://youtu.be/abc123abc12?t=125") == "abc123abc12"


def test_invalid_youtube_url_raises() -> None:
    service = YouTubeService()
    with pytest.raises(InvalidYouTubeUrlError):
        service.extract_video_id("https://example.com/watch?v=abc123abc12")
