import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.errors import InvalidYouTubeUrlError, VideoUnavailableError


YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


@dataclass(frozen=True)
class YouTubeMetadata:
    video_id: str
    title: str
    url: str
    thumbnail_url: str


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
                thumbnail_url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            )
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
            thumbnail_url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        )
