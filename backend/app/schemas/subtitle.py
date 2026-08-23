from pydantic import BaseModel


class SubtitleTokenResponse(BaseModel):
    text: str
    pinyin: str | None = None
    meaning: str | None = None
    start_index: int | None = None
    end_index: int | None = None


class SubtitleLineResponse(BaseModel):
    id: int | None = None
    start: float
    end: float
    text: str
    translation: str | None = None
    tokens: list[SubtitleTokenResponse] = []
    processing_status: str = "processed"


class SubtitleListResponse(BaseModel):
    video_id: str
    title: str | None = None
    subtitles: list[SubtitleLineResponse]


class SubtitleBatchResponse(BaseModel):
    video_id: str
    batch_index: int
    start_time: float
    end_time: float
    subtitles: list[SubtitleLineResponse]


class SubtitleProcessingProgress(BaseModel):
    video_id: str
    status: str
    phase: str = "pending"
    phase_progress: float = 0.0
    processed_batches: int
    total_batches: int
    processed_subtitles: int
    total_subtitles: int
    progress: float
