import pytest
import httpx

from app.core.errors import ASRProviderError, SubtitlesUnavailableError
from app.services.asr_service import OpenAIASRProvider
from app.services.asr_service import ASRProvider
from app.services.youtube_download_service import classify_yt_dlp_failure
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
    service.video_repo.get_by_youtube_id = lambda _video_id: _async_none()  # type: ignore[method-assign]

    lines = await service._retrieve_or_transcribe("abc123abc12", "zh")

    assert lines == [RawSubtitle(start=1.0, end=2.0, text="我在医院工作")]


async def _async_none():
    return None


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


def test_media_403_does_not_imply_invalid_cookies() -> None:
    error_class = classify_yt_dlp_failure(
        ["HTTP Error 403: Forbidden", "googlevideo media request failed"],
        RuntimeError("HTTP Error 403: Forbidden"),
    )

    assert error_class == "MEDIA_FORBIDDEN"


def test_js_challenge_failure_is_distinct_from_media_403() -> None:
    error_class = classify_yt_dlp_failure(
        ["n challenge solving failed", "Some formats may be missing"],
        RuntimeError("Requested format is not available"),
    )

    assert error_class == "JS_RUNTIME_UNAVAILABLE"


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


@pytest.mark.asyncio
async def test_openai_asr_classifies_read_timeout(tmp_path) -> None:
    provider = OpenAIASRProvider(api_key="test-key")
    audio_path = tmp_path / "audio.m4a"
    audio_path.write_bytes(b"audio")

    class TimeoutClient:
        async def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("read timed out")

    with pytest.raises(ASRProviderError) as caught:
        await provider._transcribe_file(TimeoutClient(), audio_path, "zh")

    assert caught.value.error_class == "ASR_READ_TIMEOUT"


@pytest.mark.asyncio
async def test_openai_asr_applies_chunk_timestamp_offset(monkeypatch, tmp_path) -> None:
    provider = OpenAIASRProvider(api_key="test-key")
    audio_path = tmp_path / "chunk.m4a"
    audio_path.write_bytes(b"audio")

    async def fake_transcribe(*args, **kwargs):
        return [RawSubtitle(start=1.0, end=2.5, text="测试")]

    monkeypatch.setattr(provider, "_transcribe_file", fake_transcribe)
    result = await provider._transcribe_with_retry(None, audio_path, "zh", "abc123abc12", 1, 6, 300.0, 300.0)  # type: ignore[arg-type]

    assert result == [RawSubtitle(start=301.0, end=302.5, text="测试")]
