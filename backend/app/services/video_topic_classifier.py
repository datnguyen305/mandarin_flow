import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)

VideoTopic = Literal[
    "Du lịch",
    "Ẩm thực",
    "Hội thoại",
    "Đời sống",
    "Âm nhạc",
    "Podcast",
    "Giải trí",
    "Văn hóa",
    "Học tập",
    "Công việc",
    "Tin tức",
    "Công nghệ",
    "Khác",
]


class VideoTopicClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_topic: VideoTopic
    secondary_topics: list[VideoTopic] = Field(max_length=2)
    confidence: float = Field(ge=0, le=1)

    def tags(self) -> list[str]:
        result: list[str] = []
        for topic in [self.primary_topic, *self.secondary_topics]:
            if topic not in result and (topic != "Khác" or not result):
                result.append(topic)
        return result


class VideoTopicClassifier(ABC):
    @abstractmethod
    async def classify(self, title: str, subtitles: list[str]) -> list[str]:
        raise NotImplementedError


class DisabledVideoTopicClassifier(VideoTopicClassifier):
    async def classify(self, title: str, subtitles: list[str]) -> list[str]:
        return []


class OpenAIVideoTopicClassifier(VideoTopicClassifier):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_topic_model

    async def classify(self, title: str, subtitles: list[str]) -> list[str]:
        if not self.api_key:
            logger.warning("OPENAI_API_KEY is missing; leaving video topics empty")
            return []

        sample = _subtitle_sample(subtitles)
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                result = await self._request(title, sample)
                return result.tags()
            except (httpx.HTTPError, ValueError, ValidationError) as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(1)

        logger.warning("OpenAI video topic classification failed twice; leaving topics empty: %s", last_error)
        return []

    async def _request(self, title: str, subtitles: list[str]) -> VideoTopicClassification:
        payload = {"title": title, "subtitle_sample": subtitles}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": (
                        "Classify this Chinese-learning video by subject for Vietnamese learners. "
                        "Use only the topics allowed by the JSON schema. Select one primary topic and at most "
                        "two genuinely relevant secondary topics. Do not classify by HSK level or language "
                        "difficulty. Prefer the actual content over incidental words. Use Khác only when none "
                        "of the specific topics fit. Return structured JSON only."
                    ),
                    "input": json.dumps(payload, ensure_ascii=False),
                    "temperature": 0,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "video_topic_classification",
                            "strict": True,
                            "schema": VideoTopicClassification.model_json_schema(),
                        }
                    },
                },
            )
            response.raise_for_status()
        return VideoTopicClassification.model_validate_json(_extract_output_text(response.json()))


def build_video_topic_classifier() -> VideoTopicClassifier:
    if settings.video_topic_classifier_provider.lower() == "openai":
        return OpenAIVideoTopicClassifier()
    return DisabledVideoTopicClassifier()


def _subtitle_sample(subtitles: list[str], max_lines: int = 20, max_chars: int = 4000) -> list[str]:
    result: list[str] = []
    size = 0
    for raw_text in subtitles:
        text = " ".join(raw_text.split())
        if not text:
            continue
        remaining = max_chars - size
        if remaining <= 0 or len(result) >= max_lines:
            break
        result.append(text[:remaining])
        size += len(result[-1])
    return result


def _extract_output_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks = [
        content["text"]
        for item in payload.get("output", [])
        for content in item.get("content", [])
        if isinstance(content.get("text"), str)
    ]
    if not chunks:
        raise ValueError("OpenAI video topic response did not include text output")
    return "".join(chunks)
