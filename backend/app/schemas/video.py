from datetime import datetime

from pydantic import BaseModel, HttpUrl


class ProcessVideoRequest(BaseModel):
    url: HttpUrl
    source_language: str = "zh"
    target_language: str = "vi"


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
    language: str
    processing_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaybackPositionRequest(BaseModel):
    current_time: float


class CookiesUploadRequest(BaseModel):
    content: str
