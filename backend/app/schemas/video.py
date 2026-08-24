from datetime import date, datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ProcessVideoRequest(BaseModel):
    url: HttpUrl
    source_language: str = "zh"
    target_language: str = "vi"
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            value = " ".join(tag.split())[:50]
            if value.lower().startswith(("http://", "https://")):
                raise ValueError("Video topics cannot be URLs")
            key = value.casefold()
            if value and key not in seen:
                normalized.append(value)
                seen.add(key)
        return normalized[:10]


class ProcessVideoResponse(BaseModel):
    video_id: str
    status: str
    processed_batches: int = 0
    total_batches: int = 0
    processed_subtitles: int = 0
    total_subtitles: int = 0
    progress: float = 0.0


class VideoResponse(BaseModel):
    id: int
    youtube_video_id: str
    title: str
    url: str
    thumbnail_url: str | None
    duration_seconds: int | None = None
    channel_name: str | None = None
    channel_id: str | None = None
    view_count: int | None = None
    upload_date: date | None = None
    metadata_fetched_at: datetime | None = None
    language: str
    processing_status: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaybackPositionRequest(BaseModel):
    current_time: float


class VideoProgressResponse(BaseModel):
    youtube_video_id: str
    current_time: float
    completed: bool
    last_watched_at: datetime


class CookiesUploadRequest(BaseModel):
    content: str
