import asyncio
import hashlib
import json
import logging
import unicodedata
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.config import settings
from app.db.redis import RedisCache
from app.services.pronunciation_service import PypinyinPronunciationProvider, token_pinyin
from app.services.segmentation_service import JiebaSegmentationProvider, locate_tokens

logger = logging.getLogger(__name__)


class SubtitleTokenAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    pinyin: str | None


class SubtitleSentenceAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tokens: list[SubtitleTokenAnalysis]


class SubtitleBatchAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentences: list[SubtitleSentenceAnalysis]


class SubtitleNLPProvider(ABC):
    @abstractmethod
    async def analyze_batch(self, texts: list[str]) -> list[list[SubtitleTokenAnalysis]]:
        raise NotImplementedError


class LocalSubtitleNLPProvider(SubtitleNLPProvider):
    def __init__(self) -> None:
        self.segmenter = JiebaSegmentationProvider()
        self.pronunciation = PypinyinPronunciationProvider()

    async def analyze_batch(self, texts: list[str]) -> list[list[SubtitleTokenAnalysis]]:
        segmented = self.segmenter.segment_batch(texts)
        sentence_pinyins = self.pronunciation.pinyin_batch(texts)
        return [
            [
                SubtitleTokenAnalysis(
                    text=token["text"],
                    pinyin=token_pinyin(sentence_pinyin, token["start_index"], token["end_index"]),
                )
                for token in locate_tokens(text, tokens)
            ]
            for text, tokens, sentence_pinyin in zip(texts, segmented, sentence_pinyins, strict=True)
        ]


class OpenAISubtitleNLPProvider(SubtitleNLPProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        fallback: SubtitleNLPProvider | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_nlp_model
        self.fallback = fallback or LocalSubtitleNLPProvider()

    async def analyze_batch(self, texts: list[str]) -> list[list[SubtitleTokenAnalysis]]:
        if not texts:
            return []
        if not self.api_key:
            logger.warning("OPENAI_API_KEY is missing; using local subtitle NLP fallback")
            return await self.fallback.analyze_batch(texts)

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                result = await self._request(texts)
                return self._validate_result(texts, result)
            except (httpx.HTTPError, ValueError, ValidationError) as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(1)

        logger.warning("OpenAI subtitle NLP failed twice; using local fallback: %s", last_error)
        return await self.fallback.analyze_batch(texts)

    async def _request(self, texts: list[str]) -> SubtitleBatchAnalysis:
        input_payload = {
            "sentences": [{"id": str(index), "text": text} for index, text in enumerate(texts)]
        }
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": (
                        "Segment each modern Mandarin subtitle into natural lexical words and provide contextual "
                        "tone-mark pinyin for every Chinese token. Resolve polyphonic characters from the full "
                        "sentence. Keep names and meaningful phrases intact. Exclude whitespace and punctuation "
                        "tokens. Token text must be exact substrings of the input and must preserve every "
                        "non-punctuation character in order. Join syllables inside one lexical token, for example "
                        "字幕 -> zìmù. Use null pinyin only for tokens without Chinese characters."
                    ),
                    "input": json.dumps(input_payload, ensure_ascii=False),
                    "temperature": 0,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "subtitle_linguistic_analysis",
                            "strict": True,
                            "schema": SubtitleBatchAnalysis.model_json_schema(),
                        }
                    },
                },
            )
            response.raise_for_status()
        return SubtitleBatchAnalysis.model_validate_json(_extract_output_text(response.json()))

    def _validate_result(
        self,
        texts: list[str],
        result: SubtitleBatchAnalysis,
    ) -> list[list[SubtitleTokenAnalysis]]:
        expected_ids = [str(index) for index in range(len(texts))]
        result_by_id = {sentence.id: sentence for sentence in result.sentences}
        if len(result_by_id) != len(result.sentences) or set(result_by_id) != set(expected_ids):
            raise ValueError("OpenAI subtitle NLP response IDs did not match request")

        analyzed: list[list[SubtitleTokenAnalysis]] = []
        for sentence_id, source in zip(expected_ids, texts, strict=True):
            tokens = result_by_id[sentence_id].tokens
            if not tokens or _lexical_text(source) != _lexical_text("".join(token.text for token in tokens)):
                raise ValueError(f"OpenAI subtitle NLP tokens did not cover sentence {sentence_id}")
            if any(_contains_han(token.text) and not (token.pinyin or "").strip() for token in tokens):
                raise ValueError(f"OpenAI subtitle NLP omitted pinyin for sentence {sentence_id}")
            analyzed.append(tokens)
        return analyzed


class CachedSubtitleNLPProvider(SubtitleNLPProvider):
    def __init__(self, provider: SubtitleNLPProvider, cache: RedisCache, model: str) -> None:
        self.provider = provider
        self.cache = cache
        self.model = model

    async def analyze_batch(self, texts: list[str]) -> list[list[SubtitleTokenAnalysis]]:
        digest = hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode("utf-8")).hexdigest()
        key = f"subtitle-nlp:{self.model}:{digest}"
        cached = await self.cache.get(key)
        if cached:
            try:
                return [
                    [SubtitleTokenAnalysis.model_validate(token) for token in sentence]
                    for sentence in json.loads(cached)
                ]
            except (json.JSONDecodeError, TypeError, ValidationError):
                logger.warning("Ignoring invalid cached subtitle NLP response for %s", key)

        result = await self.provider.analyze_batch(texts)
        await self.cache.set(
            key,
            json.dumps([[token.model_dump() for token in sentence] for sentence in result], ensure_ascii=False),
        )
        return result


def build_subtitle_nlp_provider(cache: RedisCache) -> SubtitleNLPProvider:
    if settings.subtitle_nlp_provider.lower() == "openai":
        provider: SubtitleNLPProvider = OpenAISubtitleNLPProvider()
    else:
        provider = LocalSubtitleNLPProvider()
    return CachedSubtitleNLPProvider(provider, cache, settings.openai_nlp_model)


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
        raise ValueError("OpenAI subtitle NLP response did not include text output")
    return "".join(chunks)


def _lexical_text(text: str) -> str:
    return "".join(char for char in text if not char.isspace() and not unicodedata.category(char).startswith("P"))


def _contains_han(text: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff" for char in text)
