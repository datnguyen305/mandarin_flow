import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.errors import ASRProviderError
from app.services.cookie_session import CookieSessionStore

logger = logging.getLogger(__name__)


class YtDlpLogCollector:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def debug(self, message: str) -> None:
        logger.debug("yt-dlp: %s", _redact(message))

    def info(self, message: str) -> None:
        logger.info("yt-dlp: %s", _redact(message))

    def warning(self, message: str) -> None:
        message = _redact(message)
        self.messages.append(message)
        logger.warning("yt-dlp: %s", message)

    def error(self, message: str) -> None:
        message = _redact(message)
        self.messages.append(message)
        logger.error("yt-dlp: %s", message)


@dataclass(frozen=True)
class DownloadDiagnostics:
    error_class: str
    cookie_status: str
    player_client: str
    po_provider_available: bool
    attempt: int


def _redact(message: str) -> str:
    message = re.sub(r"https?://\S+", "<url>", message)
    message = re.sub(r"(?:Bearer|Authorization)\s+\S+", "<redacted>", message, flags=re.IGNORECASE)
    return message


def classify_yt_dlp_failure(messages: list[str], exc: Exception) -> str:
    combined = "\n".join([*messages, str(exc)]).lower()
    if "video unavailable" in combined or "private video" in combined or "has been removed" in combined:
        return "VIDEO_UNAVAILABLE"
    if "sign in to confirm your age" in combined or "age-restricted" in combined:
        return "AGE_RESTRICTED"
    if "not available in your country" in combined or "geo-restricted" in combined:
        return "GEO_RESTRICTED"
    if "sign in" in combined and ("cookies" in combined or "login" in combined):
        return "LOGIN_REQUIRED"
    if "account cookies are no longer valid" in combined or "cookies are no longer valid" in combined:
        return "COOKIE_INVALID"
    if "n challenge solving failed" in combined or "signature solving failed" in combined:
        return "JS_RUNTIME_UNAVAILABLE"
    if "requested format is not available" in combined or "only images are available" in combined:
        return "PLAYBACK_FORMAT_UNAVAILABLE"
    if "429" in combined or "too many requests" in combined or "rate limit" in combined:
        return "RATE_LIMITED"
    if "timed out" in combined or "timeout" in combined or "connection reset" in combined:
        return "NETWORK_ERROR"
    if "403" in combined or "forbidden" in combined or "googlevideo" in combined:
        return "MEDIA_FORBIDDEN"
    return "UNKNOWN"


class YouTubeAudioDownloader:
    def __init__(self, max_duration_seconds: int | None = None) -> None:
        self.max_attempts = max(1, settings.yt_dlp_max_attempts)
        self.max_duration_seconds = max_duration_seconds or settings.asr_max_duration_seconds

    def download(self, youtube_video_id: str, output_dir: Path, downloader_class=None) -> tuple[Path, DownloadDiagnostics]:
        if downloader_class is None:
            try:
                from yt_dlp import YoutubeDL
            except Exception as exc:
                raise ASRProviderError("yt-dlp is required for YouTube audio extraction") from exc
            downloader_class = YoutubeDL

        output_template = str(output_dir / "%(id)s.%(ext)s")
        url = f"https://www.youtube.com/watch?v={youtube_video_id}"
        last_diagnostics: DownloadDiagnostics | None = None

        for attempt in range(1, self.max_attempts + 1):
            collector = YtDlpLogCollector()
            options: dict[str, Any] = {
                "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
                "outtmpl": output_template,
                "quiet": True,
                "noplaylist": True,
                "retries": 1,
                "fragment_retries": 1,
                "socket_timeout": settings.yt_dlp_socket_timeout,
                "concurrent_fragment_downloads": 1,
                "logger": collector,
                "http_headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            }
            if settings.yt_dlp_js_runtime_path:
                options["js_runtimes"] = {"deno": {"path": settings.yt_dlp_js_runtime_path}}
            if settings.yt_dlp_remote_components:
                options["remote_components"] = {settings.yt_dlp_remote_components}
            if settings.yt_dlp_player_client:
                options["extractor_args"] = {"youtube": {"player_client": [settings.yt_dlp_player_client]}}

            cookies_path = Path(settings.yt_dlp_cookies_file) if settings.yt_dlp_cookies_file else None
            cookie_session = CookieSessionStore(cookies_path if cookies_path and cookies_path.exists() else None)
            if cookies_path and cookies_path.exists():
                writable_cookies_path = output_dir / "cookies.txt"
                writable_cookies_path.write_bytes(cookies_path.read_bytes())
                writable_cookies_path.chmod(0o600)
                options["cookiefile"] = str(writable_cookies_path)

            try:
                with downloader_class(options) as downloader:
                    info = downloader.extract_info(url, download=False)
                    duration = int(info.get("duration") or 0)
                    cookie_session.mark_probe_success()
                    if duration and duration > self.max_duration_seconds:
                        raise ASRProviderError(
                            f"Video is {duration} seconds long; ASR limit is "
                            f"{self.max_duration_seconds} seconds for this MVP."
                        )
                    downloader.download([url])
                cookie_session.mark_download_success()
                audio_path = self._find_audio(output_dir)
                diagnostics = DownloadDiagnostics(
                    error_class="NONE",
                    cookie_status="valid" if cookies_path else "unknown",
                    player_client=settings.yt_dlp_player_client or "default",
                    po_provider_available=False,
                    attempt=attempt,
                )
                logger.info("youtube audio download succeeded", extra={"youtube_id": youtube_video_id, **diagnostics.__dict__})
                return audio_path, diagnostics
            except ASRProviderError:
                raise
            except Exception as exc:
                error_class = classify_yt_dlp_failure(collector.messages, exc)
                cookie_status = "invalid" if error_class in {"COOKIE_INVALID", "LOGIN_REQUIRED"} else "valid" if cookies_path else "unknown"
                last_diagnostics = DownloadDiagnostics(
                    error_class=error_class,
                    cookie_status=cookie_status,
                    player_client=settings.yt_dlp_player_client or "default",
                    po_provider_available=False,
                    attempt=attempt,
                )
                logger.warning(
                    "youtube audio download failed",
                    extra={"youtube_id": youtube_video_id, **last_diagnostics.__dict__},
                )
                if error_class in {"COOKIE_INVALID", "LOGIN_REQUIRED"}:
                    cookie_session.mark_needs_refresh(error_class)
                elif error_class == "MEDIA_FORBIDDEN":
                    cookie_session.mark_media_error(error_class)
                if error_class not in {"NETWORK_ERROR", "RATE_LIMITED", "MEDIA_FORBIDDEN"} or attempt >= self.max_attempts:
                    break
                time.sleep(settings.yt_dlp_retry_backoff_seconds * attempt)

        assert last_diagnostics is not None
        messages = {
            "COOKIE_INVALID": "YouTube cookies are expired or invalid and require refresh.",
            "LOGIN_REQUIRED": "YouTube requires an authenticated session.",
            "MEDIA_FORBIDDEN": "Could not download YouTube audio: YouTube rejected the media request (403 Forbidden). The session may still be valid; playback client or PO Token requirements need investigation.",
            "JS_RUNTIME_UNAVAILABLE": "YouTube playback challenge could not be solved. Check the configured JavaScript runtime and yt-dlp EJS components.",
            "PLAYBACK_FORMAT_UNAVAILABLE": "YouTube returned no downloadable audio format after playback challenges.",
            "VIDEO_UNAVAILABLE": "The YouTube video is unavailable.",
            "AGE_RESTRICTED": "The YouTube video is age restricted.",
            "GEO_RESTRICTED": "The YouTube video is geo restricted.",
            "RATE_LIMITED": "YouTube rate-limited the audio request.",
            "NETWORK_ERROR": "The YouTube audio request timed out or failed at the network layer.",
        }
        raise ASRProviderError(
            messages.get(last_diagnostics.error_class, "Could not download YouTube audio."),
            error_class=last_diagnostics.error_class,
        )

    def _find_audio(self, output_dir: Path) -> Path:
        suffixes = {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".wav", ".webm"}
        matches = [path for path in output_dir.iterdir() if path.is_file() and path.suffix.lower() in suffixes]
        if not matches:
            raise ASRProviderError("Could not find a supported downloaded YouTube audio file for ASR")
        return max(matches, key=lambda path: path.stat().st_size)
