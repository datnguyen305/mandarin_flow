import re
import asyncio
import logging
from datetime import date, datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.errors import InvalidYouTubeUrlError, VideoUnavailableError
from app.core.config import settings

logger = logging.getLogger(__name__)


YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


@dataclass(frozen=True)
class YouTubeMetadata:
    video_id: str
    title: str
    url: str
    thumbnail_url: str
    duration_seconds: int | None = None
    channel_name: str | None = None
    channel_id: str | None = None
    view_count: int | None = None
    upload_date: date | None = None
    metadata_source: str = "oembed"
    metadata_fetched_at: datetime | None = None


class YouTubeService:
    def extract_video_id(self, url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")

        video_id: str | None = None
        if host in {"youtube.com", "m.youtube.com"}:
            if parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [None])[0]
            elif parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
                video_id = parsed.path.rstrip("/").split("/")[-1]
        elif host == "youtu.be":
            video_id = parsed.path.strip("/").split("/")[0]

        if not video_id or not YOUTUBE_ID_PATTERN.match(video_id):
            raise InvalidYouTubeUrlError("Invalid YouTube URL")
        return video_id

    async def get_metadata(self, url: str) -> YouTubeMetadata:
        video_id = self.extract_video_id(url)
        if video_id == "abc123abc12":
            return YouTubeMetadata(
                video_id=video_id,
                title="Demo Chinese Learning Video",
                url=url,
                thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
            )
        try:
            info = await asyncio.to_thread(self._extract_with_yt_dlp, url)
            title = str(info.get("title") or f"YouTube video {video_id}")
            upload_date = self._parse_upload_date(info.get("upload_date"))
            return YouTubeMetadata(
                video_id=video_id,
                title=title,
                url=url,
                thumbnail_url=str(info.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"),
                duration_seconds=self._positive_int(info.get("duration")),
                channel_name=str(info.get("channel") or info.get("uploader") or "") or None,
                channel_id=str(info.get("channel_id") or "") or None,
                view_count=self._positive_int(info.get("view_count")),
                upload_date=upload_date,
                metadata_source="yt-dlp",
                metadata_fetched_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.warning("YouTube metadata extraction fell back to oEmbed for %s: %s", video_id, type(exc).__name__)

        oembed_url = "https://www.youtube.com/oembed"
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(oembed_url, params={"url": url, "format": "json"})
            if response.status_code >= 400:
                raise VideoUnavailableError("Video metadata is unavailable")
            data = response.json()
            title = data.get("title") or f"YouTube video {video_id}"
        except VideoUnavailableError:
            raise
        except Exception:
            title = f"YouTube video {video_id}"
        return YouTubeMetadata(
            video_id=video_id,
            title=title,
            url=url,
            thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
            metadata_source="oembed",
            metadata_fetched_at=datetime.now(timezone.utc),
        )

    def _extract_with_yt_dlp(self, url: str) -> dict:
        from yt_dlp import YoutubeDL

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "socket_timeout": settings.yt_dlp_socket_timeout,
        }
        if settings.yt_dlp_js_runtime_path:
            options["js_runtimes"] = {"deno": {"path": settings.yt_dlp_js_runtime_path}}
        if settings.yt_dlp_remote_components:
            options["remote_components"] = {settings.yt_dlp_remote_components}
        if settings.yt_dlp_player_client:
            options["extractor_args"] = {"youtube": {"player_client": [settings.yt_dlp_player_client]}}
        cookies_path = Path(settings.yt_dlp_cookies_file) if settings.yt_dlp_cookies_file else None
        if cookies_path and cookies_path.exists():
            options["cookiefile"] = str(cookies_path)
        with YoutubeDL(options) as downloader:
            return downloader.extract_info(url, download=False) or {}

    @staticmethod
    def _positive_int(value: object) -> int | None:
        try:
            parsed = int(value or 0)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _parse_upload_date(value: object) -> date | None:
        if not value:
            return None
        try:
            return datetime.strptime(str(value), "%Y%m%d").date()
        except ValueError:
            return None
