from datetime import datetime

from pydantic import BaseModel


class SaveVocabularyRequest(BaseModel):
    word: str
    pinyin: str | None = None
    meaning: str | None = None
    youtube_video_id: str
    subtitle_id: int
    timestamp: float


class SavedVocabularyResponse(BaseModel):
    id: int
    word: str
    pinyin: str | None
    meaning: str | None
    youtube_video_id: str
    video_title: str
    subtitle_sentence: str
    timestamp: float
    created_at: datetime


class SaveVocabularyResponse(BaseModel):
    id: int
    status: str
