from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class VideoAgentRequest(BaseModel):
    youtube_url: HttpUrl
    reason: str = Field(min_length=1, max_length=2000)
    suggested_tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("suggested_tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            value = " ".join(value.split())[:50]
            if value and value.casefold() not in {item.casefold() for item in result}:
                result.append(value)
        return result


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatAgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatAgentResponse(BaseModel):
    reply: str
    youtube_url: str | None = None
    imported_video_id: str | None = None
    import_status: str | None = None
    pending_action: dict[str, Any] | None = None


class VocabularyAgentItem(BaseModel):
    simplified: str = Field(min_length=1, max_length=128)
    traditional: str | None = Field(default=None, max_length=128)
    pinyin: str | None = Field(default=None, max_length=256)
    pinyin_number: str | None = Field(default=None, max_length=256)
    vi: str | None = Field(default=None, max_length=500)
    pos: str | None = Field(default=None, max_length=64)
    definition_vi: str | None = Field(default=None, max_length=2000)
    hsk: int | None = Field(default=None, ge=1, le=9)
    examples: list[dict[str, Any]] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def default_traditional(self):
        if not self.traditional:
            self.traditional = self.simplified
        return self


class VocabularyAgentRequest(BaseModel):
    words: list[VocabularyAgentItem] = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=2000)


class CookieAgentRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    youtube_url: HttpUrl | None = None


class CookieExportResult(BaseModel):
    success: bool
    error: str | None = Field(default=None, max_length=2000)


class AgentRequestResponse(BaseModel):
    request_id: str | None = None
    status: Literal["pending_approval", "notification_failed", "already_exists", "manual_action_required", "limit_reached"]
    skipped_count: int = 0


class AgentRequestView(BaseModel):
    id: str
    type: str
    status: str
    payload: dict[str, Any]
    reason: str
    requested_by: str
    approved_by: str | None
    error: str | None
    created_at: datetime
    approved_at: datetime | None
    rejected_at: datetime | None
    executed_at: datetime | None
    expires_at: datetime

    model_config = {"from_attributes": True}
