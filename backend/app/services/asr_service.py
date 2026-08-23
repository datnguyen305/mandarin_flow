import asyncio
import logging
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.errors import ASRProviderError, SubtitlesUnavailableError
from app.services.transcript_types import RawSubtitle
from app.services.youtube_download_service import YouTubeAudioDownloader

logger = logging.getLogger(__name__)
ASRProgressCallback = Callable[[int, int], Awaitable[None]]
TRANSIENT_ASR_ERRORS = {"ASR_CONNECT_TIMEOUT", "ASR_READ_TIMEOUT", "ASR_WRITE_TIMEOUT", "ASR_NETWORK_ERROR", "ASR_RATE_LIMIT"}


class ASRProvider(ABC):
    @abstractmethod
    async def transcribe_youtube_audio(self, youtube_video_id: str, language: str, progress_callback: ASRProgressCallback | None = None) -> list[RawSubtitle]:
        raise NotImplementedError


class DisabledASRProvider(ASRProvider):
    async def transcribe_youtube_audio(self, youtube_video_id: str, language: str, progress_callback=None) -> list[RawSubtitle]:
        raise SubtitlesUnavailableError("Chinese subtitles are unavailable for this video. ASR is not enabled.")


class OpenAIASRProvider(ASRProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None, max_duration_seconds: int | None = None) -> None:
        self.api_key = api_key or settings.openai_asr_api_key or settings.openai_api_key
        self.model = model or settings.openai_asr_model
        self.max_duration_seconds = max_duration_seconds or settings.asr_max_duration_seconds

    async def transcribe_youtube_audio(self, youtube_video_id: str, language: str, progress_callback: ASRProgressCallback | None = None) -> list[RawSubtitle]:
        if not self.api_key:
            raise ASRProviderError("OPENAI_ASR_API_KEY is required when ASR_PROVIDER=openai", "ASR_API_ERROR")
        with tempfile.TemporaryDirectory(prefix="youtube-asr-") as temp_dir:
            output_dir = Path(temp_dir)
            audio_path = await asyncio.to_thread(self._download_audio, youtube_video_id, output_dir)
            duration = await asyncio.to_thread(self._probe_duration, audio_path)
            size_bytes = audio_path.stat().st_size
            logger.info("ASR input prepared", extra={"youtube_id": youtube_video_id, "audio_duration_seconds": round(duration, 2), "audio_size_bytes": size_bytes, "model": self.model})
            chunk_seconds = settings.asr_chunk_duration_seconds
            chunk_count = 1 if duration <= chunk_seconds else int((duration + chunk_seconds - 1) // chunk_seconds)
            subtitles: list[RawSubtitle] = []
            async with self._client() as client:
                for chunk_index in range(chunk_count):
                    start = 0.0 if chunk_count == 1 else chunk_index * chunk_seconds
                    chunk_duration = duration if chunk_count == 1 else min(chunk_seconds, duration - start)
                    path = audio_path
                    if chunk_count > 1:
                        path = output_dir / f"chunk-{chunk_index:04d}.m4a"
                        await asyncio.to_thread(self._create_chunk, audio_path, path, start, chunk_duration)
                    try:
                        subtitles.extend(await self._transcribe_with_retry(client, path, language, youtube_video_id, chunk_index, chunk_count, start, chunk_duration))
                    finally:
                        if path != audio_path:
                            path.unlink(missing_ok=True)
                    if progress_callback:
                        await progress_callback(chunk_index + 1, chunk_count)
            return subtitles

    def _download_audio(self, youtube_video_id: str, output_dir: Path) -> Path:
        return YouTubeAudioDownloader(max_duration_seconds=self.max_duration_seconds).download(youtube_video_id, output_dir, self._downloader_class())[0]

    @staticmethod
    def _find_downloaded_audio_file(output_dir: Path) -> Path:
        matches = [path for path in output_dir.iterdir() if path.is_file() and path.suffix.lower() in {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".wav", ".webm"}]
        if not matches:
            raise ASRProviderError("Could not find a supported downloaded YouTube audio file for ASR", "ASR_INVALID_AUDIO")
        return max(matches, key=lambda path: path.stat().st_size)

    @staticmethod
    def _downloader_class():
        try:
            from yt_dlp import YoutubeDL
            return YoutubeDL
        except Exception as exc:
            raise ASRProviderError("yt-dlp is required for YouTube audio extraction", "ASR_INVALID_AUDIO") from exc

    @staticmethod
    def _probe_duration(audio_path: Path) -> float:
        try:
            result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)], check=True, capture_output=True, text=True)
            duration = float(result.stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise ASRProviderError("Could not inspect ASR audio duration", "ASR_INVALID_AUDIO") from exc
        if duration <= 0:
            raise ASRProviderError("ASR audio duration is invalid", "ASR_INVALID_AUDIO")
        return duration

    @staticmethod
    def _create_chunk(source: Path, destination: Path, start: float, duration: float) -> None:
        try:
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{duration:.3f}", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "aac", "-b:a", "64k", str(destination)], check=True, capture_output=True, text=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ASRProviderError("Could not split audio for ASR", "ASR_INVALID_AUDIO") from exc

    @staticmethod
    def _client() -> httpx.AsyncClient:
        timeout = httpx.Timeout(timeout=None, connect=settings.asr_connect_timeout_seconds, read=settings.asr_read_timeout_seconds, write=settings.asr_write_timeout_seconds, pool=settings.asr_pool_timeout_seconds)
        return httpx.AsyncClient(timeout=timeout)

    async def _transcribe_with_retry(self, client: httpx.AsyncClient, audio_path: Path, language: str, youtube_video_id: str, chunk_index: int, chunk_count: int, start_offset: float, duration: float) -> list[RawSubtitle]:
        max_attempts = max(1, settings.asr_max_attempts_per_chunk)
        for attempt in range(1, max_attempts + 1):
            started = time.monotonic()
            try:
                result = await self._transcribe_file(client, audio_path, language)
                logger.info("ASR chunk succeeded", extra={"youtube_id": youtube_video_id, "chunk_index": chunk_index, "chunk_count": chunk_count, "attempt": attempt, "elapsed_seconds": round(time.monotonic() - started, 2), "audio_duration_seconds": round(duration, 2), "audio_size_bytes": audio_path.stat().st_size, "model": self.model})
                return [RawSubtitle(item.start + start_offset, item.end + start_offset, item.text) for item in result]
            except ASRProviderError as exc:
                logger.warning("ASR chunk failed", extra={"youtube_id": youtube_video_id, "chunk_index": chunk_index, "chunk_count": chunk_count, "attempt": attempt, "elapsed_seconds": round(time.monotonic() - started, 2), "audio_duration_seconds": round(duration, 2), "audio_size_bytes": audio_path.stat().st_size, "model": self.model, "error_class": exc.error_class, "exception_type": type(exc.__cause__ or exc).__name__, "exception_message": str(exc.__cause__ or exc)[:200]})
                if exc.error_class not in TRANSIENT_ASR_ERRORS or attempt >= max_attempts:
                    raise
                await asyncio.sleep(settings.asr_retry_backoff_seconds * (2 ** (attempt - 1)))
        raise AssertionError("ASR retry loop unexpectedly completed")

    async def _transcribe_file(self, client: httpx.AsyncClient, audio_path: Path, language: str) -> list[RawSubtitle]:
        try:
            with audio_path.open("rb") as audio_file:
                response = await client.post("https://api.openai.com/v1/audio/transcriptions", headers={"Authorization": f"Bearer {self.api_key}"}, data={"model": self.model, "language": language, "response_format": "verbose_json", "timestamp_granularities[]": "segment"}, files={"file": (audio_path.name, audio_file, "audio/mp4")})
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            error_class = "ASR_RATE_LIMIT" if code == 429 else "ASR_FILE_TOO_LARGE" if code == 413 else "ASR_INVALID_AUDIO" if code == 400 else "ASR_API_ERROR"
            logger.warning("OpenAI ASR API error", extra={"status_code": code, "error_class": error_class, "model": self.model})
            raise ASRProviderError(self._openai_error_message(exc.response), error_class) from exc
        except httpx.ConnectTimeout as exc:
            raise ASRProviderError("OpenAI ASR connect timeout", "ASR_CONNECT_TIMEOUT") from exc
        except httpx.ReadTimeout as exc:
            raise ASRProviderError("OpenAI ASR read timeout", "ASR_READ_TIMEOUT") from exc
        except httpx.WriteTimeout as exc:
            raise ASRProviderError("OpenAI ASR upload timeout", "ASR_WRITE_TIMEOUT") from exc
        except httpx.PoolTimeout as exc:
            raise ASRProviderError("OpenAI ASR connection pool timeout", "ASR_NETWORK_ERROR") from exc
        except httpx.ConnectError as exc:
            raise ASRProviderError("OpenAI ASR network connection failed", "ASR_NETWORK_ERROR") from exc
        except httpx.HTTPError as exc:
            raise ASRProviderError("OpenAI ASR network request failed", "ASR_NETWORK_ERROR") from exc
        except Exception as exc:
            raise ASRProviderError("OpenAI ASR request failed", "ASR_UNKNOWN_ERROR") from exc
        data = response.json()
        segments = data.get("segments") or []
        if segments:
            return [RawSubtitle(float(item["start"]), float(item["end"]), str(item["text"]).strip()) for item in segments if str(item.get("text", "")).strip()]
        text = str(data.get("text", "")).strip()
        if text:
            return [RawSubtitle(0.0, 0.0, text)]
        raise ASRProviderError("OpenAI ASR returned no transcript text", "ASR_API_ERROR")

    @staticmethod
    def _openai_error_message(response: httpx.Response) -> str:
        try:
            message = response.json().get("error", {}).get("message")
            if message:
                return f"OpenAI ASR request failed: {message}"
        except ValueError:
            pass
        return f"OpenAI ASR request failed with HTTP {response.status_code}"


def build_asr_provider() -> ASRProvider:
    if settings.asr_provider.lower() == "openai":
        return OpenAIASRProvider()
    return DisabledASRProvider()
