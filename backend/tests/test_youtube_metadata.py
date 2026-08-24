import asyncio
from datetime import date
import sys
import types

import pytest

from app.services.youtube_service import YouTubeService


@pytest.mark.asyncio
async def test_get_metadata_uses_ytdlp_without_downloading(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def extract_info(self, url, download=False):
            calls.append((url, download))
            return {
                "id": "TOC78RUj8pg",
                "title": "Test lesson",
                "thumbnail": "https://example.test/thumb.jpg",
                "duration": 123.8,
                "channel": "MandarinFlow",
                "channel_id": "UC123",
                "upload_date": "20260823",
            }

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYoutubeDL))

    async def run_inline(function, *args):
        return function(*args)

    monkeypatch.setattr(asyncio, "to_thread", run_inline)

    metadata = await YouTubeService().get_metadata("https://www.youtube.com/watch?v=TOC78RUj8pg")

    assert calls == [("https://www.youtube.com/watch?v=TOC78RUj8pg", False)]
    assert metadata.metadata_source == "yt-dlp"
    assert metadata.duration_seconds == 123
    assert metadata.channel_name == "MandarinFlow"
    assert metadata.channel_id == "UC123"
    assert metadata.upload_date == date(2026, 8, 23)


def test_metadata_helpers_ignore_invalid_values() -> None:
    assert YouTubeService._positive_int("not-a-number") is None
    assert YouTubeService._parse_upload_date("20261399") is None
