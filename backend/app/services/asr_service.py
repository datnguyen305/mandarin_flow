import asyncio
import logging
import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import ASRProviderError, SubtitlesUnavailableError
from app.services.transcript_types import RawSubtitle

logger = logging.getLogger(__name__)

SUPPORTED_ASR_AUDIO_SUFFIXES = {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".wav", ".webm"}


class YtDlpLogCollector:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def debug(self, message: str) -> None:
        logger.debug("yt-dlp: %s", message)

    def info(self, message: str) -> None:
        logger.info("yt-dlp: %s", message)

    def warning(self, message: str) -> None:
        self.messages.append(message)
        logger.warning("yt-dlp: %s", message)

    def error(self, message: str) -> None:
        self.messages.append(message)
        logger.error("yt-dlp: %s", message)


class ASRProvider(ABC):
    @abstractmethod
    async def transcribe_youtube_audio(self, youtube_video_id: str, language: str) -> list[RawSubtitle]:
        raise NotImplementedError


class DisabledASRProvider(ASRProvider):
    async def transcribe_youtube_audio(self, youtube_video_id: str, language: str) -> list[RawSubtitle]:
        raise SubtitlesUnavailableError("Chinese subtitles are unavailable for this video. ASR is not enabled.")


class OpenAIASRProvider(ASRProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_duration_seconds: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_asr_model
        self.max_duration_seconds = max_duration_seconds or settings.asr_max_duration_seconds

    async def transcribe_youtube_audio(self, youtube_video_id: str, language: str) -> list[RawSubtitle]:
        if not self.api_key:
            raise ASRProviderError("OPENAI_API_KEY is required when ASR_PROVIDER=openai")

        with tempfile.TemporaryDirectory(prefix="youtube-asr-") as temp_dir:
            audio_path = await asyncio.to_thread(self._download_audio, youtube_video_id, Path(temp_dir))
            return await self._transcribe_file(audio_path, language)

    def _download_audio(self, youtube_video_id: str, output_dir: Path) -> Path:
        url = f"https://www.youtube.com/watch?v={youtube_video_id}"
        output_template = str(output_dir / "%(id)s.%(ext)s")
        options: dict[str, Any] = {
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
            "outtmpl": output_template,
            "quiet": True,
            "noplaylist": True,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            },
        }
        if settings.yt_dlp_cookies_file:
            cookies_path = Path(settings.yt_dlp_cookies_file)
            if cookies_path.exists():
                writable_cookies_path = output_dir / "cookies.txt"
                shutil.copyfile(cookies_path, writable_cookies_path)
                options["cookiefile"] = str(writable_cookies_path)
            else:
                logger.warning("YT_DLP_COOKIES_FILE is set but file does not exist: %s", cookies_path)

        ytdlp_logger = YtDlpLogCollector()
        options["logger"] = ytdlp_logger

        try:
            with self._downloader_class()(options) as downloader:
                info = downloader.extract_info(url, download=False)
                duration = int(info.get("duration") or 0)
                if duration and duration > self.max_duration_seconds:
                    raise ASRProviderError(
                        f"Video is {duration} seconds long; ASR limit is {self.max_duration_seconds} seconds for this MVP."
                    )
                downloader.download([url])
        except ASRProviderError:
            raise
        except Exception as exc:
            logger.warning("yt-dlp download failed for %s: %r", youtube_video_id, exc)
            raise ASRProviderError(self._download_error_message(exc, ytdlp_logger.messages)) from exc

        return self._find_downloaded_audio_file(output_dir)

    def _find_downloaded_audio_file(self, output_dir: Path) -> Path:
        matches = [
            path
            for path in output_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_ASR_AUDIO_SUFFIXES
        ]
        if not matches:
            logger.warning("yt-dlp reported success but no supported audio file was found in %s", output_dir)
            raise ASRProviderError("Could not find a supported downloaded YouTube audio file for ASR")
        return max(matches, key=lambda path: path.stat().st_size)

    def _downloader_class(self):
        try:
            from yt_dlp import YoutubeDL
        except Exception as exc:
            raise ASRProviderError("yt-dlp is required for YouTube audio extraction") from exc
        return YoutubeDL

    def _download_error_message(self, exc: Exception, ytdlp_messages: list[str]) -> str:
        combined = "\n".join([*ytdlp_messages, repr(exc)]).lower()
        if "cookies are no longer valid" in combined or "account cookies are no longer valid" in combined:
            return (
                "Could not download YouTube audio for ASR because the YouTube cookies are expired or invalid. "
                "Export fresh cookies from the same browser/account and save them to cookies/cookies.txt, then restart the backend."
            )
        if "403" in combined or "forbidden" in combined:
            return (
                "Could not download YouTube audio for ASR because YouTube returned 403 Forbidden. "
                "This usually means the video requires fresh browser cookies, the account cannot access the video, or automated downloads are restricted."
            )
        return (
            "Could not download YouTube audio for ASR. YouTube may block this video, require cookies, or restrict automated downloads."
        )

    async def _transcribe_file(self, audio_path: Path, language: str) -> list[RawSubtitle]:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                with audio_path.open("rb") as audio_file:
                    response = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        data={
                            "model": self.model,
                            "language": language,
                            "response_format": "verbose_json",
                            "timestamp_granularities[]": "segment",
                        },
                        files={"file": (audio_path.name, audio_file, "application/octet-stream")},
                    )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("OpenAI ASR failed: %s", exc.response.text)
            raise ASRProviderError(self._openai_error_message(exc.response)) from exc
        except Exception as exc:
            raise ASRProviderError("OpenAI ASR request failed") from exc

        data = response.json()
        segments = data.get("segments") or []
        if segments:
            return [
                RawSubtitle(
                    start=float(segment["start"]),
                    end=float(segment["end"]),
                    text=str(segment["text"]).strip(),
                )
                for segment in segments
                if str(segment.get("text", "")).strip()
            ]

        text = str(data.get("text", "")).strip()
        if text:
            return [RawSubtitle(start=0.0, end=0.0, text=text)]
        raise ASRProviderError("OpenAI ASR returned no transcript text")

    def _openai_error_message(self, response: httpx.Response) -> str:
        try:
            body = response.json()
            message = body.get("error", {}).get("message")
            if message:
                return f"OpenAI ASR request failed: {message}"
        except ValueError:
            pass
        return f"OpenAI ASR request failed with HTTP {response.status_code}"


def build_asr_provider() -> ASRProvider:
    if settings.asr_provider.lower() == "openai":
        return OpenAIASRProvider()
    return DisabledASRProvider()
