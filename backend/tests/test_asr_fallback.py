import pytest
import httpx

from app.core.errors import ASRProviderError, SubtitlesUnavailableError
from app.services.asr_service import OpenAIASRProvider
from app.services.asr_service import ASRProvider
from app.services.subtitle_service import RawSubtitle, SubtitleRetrievalProvider, SubtitleService


class MissingSubtitleProvider(SubtitleRetrievalProvider):
    async def fetch(self, youtube_video_id: str, language: str) -> list[RawSubtitle]:
        raise SubtitlesUnavailableError("missing")


class FakeASRProvider(ASRProvider):
    async def transcribe_youtube_audio(self, youtube_video_id: str, language: str) -> list[RawSubtitle]:
        return [RawSubtitle(start=1.0, end=2.0, text="我在医院工作")]


@pytest.mark.asyncio
async def test_retrieve_or_transcribe_falls_back_to_asr() -> None:
    service = SubtitleService(
        db=None,  # type: ignore[arg-type]
        cache=None,  # type: ignore[arg-type]
        youtube_service=None,  # type: ignore[arg-type]
        subtitle_provider=MissingSubtitleProvider(),
        asr_provider=FakeASRProvider(),
        segmentation_provider=None,  # type: ignore[arg-type]
        translation_provider=None,  # type: ignore[arg-type]
        dictionary_provider=None,  # type: ignore[arg-type]
    )

    lines = await service._retrieve_or_transcribe("abc123abc12", "zh")

    assert lines == [RawSubtitle(start=1.0, end=2.0, text="我在医院工作")]


def test_openai_asr_wraps_download_errors(monkeypatch, tmp_path) -> None:
    provider = OpenAIASRProvider(api_key="test-key")

    class BrokenDownloader:
        def __init__(self, options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def extract_info(self, url, download=False):
            return {"duration": 10}

        def download(self, urls):
            raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(provider, "_downloader_class", lambda: BrokenDownloader)

    with pytest.raises(ASRProviderError, match="Could not download YouTube audio"):
        provider._download_audio("abc123abc12", tmp_path)


def test_openai_asr_reports_invalid_cookies(monkeypatch, tmp_path) -> None:
    provider = OpenAIASRProvider(api_key="test-key")

    class BrokenDownloader:
        def __init__(self, options):
            options["logger"].warning("The provided YouTube account cookies are no longer valid.")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def extract_info(self, url, download=False):
            return {"duration": 10}

        def download(self, urls):
            raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(provider, "_downloader_class", lambda: BrokenDownloader)

    with pytest.raises(ASRProviderError, match="cookies are expired or invalid"):
        provider._download_audio("abc123abc12", tmp_path)


def test_openai_asr_allows_videos_up_to_30_minutes(monkeypatch, tmp_path) -> None:
    provider = OpenAIASRProvider(api_key="test-key", max_duration_seconds=1800)

    class Downloader:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def extract_info(self, url, download=False):
            return {"duration": 1800}

        def download(self, urls):
            (tmp_path / "abc123abc12.m4a").write_bytes(b"audio")

    monkeypatch.setattr(provider, "_downloader_class", lambda: Downloader)

    assert provider._download_audio("abc123abc12", tmp_path).name == "abc123abc12.m4a"


def test_openai_asr_rejects_videos_over_30_minutes(monkeypatch, tmp_path) -> None:
    provider = OpenAIASRProvider(api_key="test-key", max_duration_seconds=1800)

    class Downloader:
        def __init__(self, options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def extract_info(self, url, download=False):
            return {"duration": 1801}

        def download(self, urls):
            raise AssertionError("download should not run for videos over the limit")

    monkeypatch.setattr(provider, "_downloader_class", lambda: Downloader)

    with pytest.raises(ASRProviderError, match="ASR limit is 1800 seconds"):
        provider._download_audio("abc123abc12", tmp_path)


def test_openai_asr_ignores_cookies_file_when_selecting_download(tmp_path) -> None:
    provider = OpenAIASRProvider(api_key="test-key")
    cookies_path = tmp_path / "cookies.txt"
    audio_path = tmp_path / "abc123abc12.m4a"
    cookies_path.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    audio_path.write_bytes(b"audio")

    assert provider._find_downloaded_audio_file(tmp_path) == audio_path


def test_openai_asr_reports_openai_error_message() -> None:
    provider = OpenAIASRProvider(api_key="test-key")
    response = httpx.Response(
        400,
        json={"error": {"message": "Invalid file format."}},
        request=httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions"),
    )

    assert provider._openai_error_message(response) == "OpenAI ASR request failed: Invalid file format."
