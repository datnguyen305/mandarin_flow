import hashlib
import json
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings
from app.core.errors import TranslationProviderError
from app.db.redis import RedisCache


class TranslationProvider(ABC):
    @abstractmethod
    async def translate_batch(self, texts: list[str], source_language: str, target_language: str) -> list[str]:
        raise NotImplementedError


class LocalTranslationProvider(TranslationProvider):
    phrase_map = {
        "我今天在医院工作。": "Hôm nay tôi làm việc ở bệnh viện.",
        "我在医院工作": "Tôi làm việc ở bệnh viện",
        "我在医院工作。": "Tôi làm việc ở bệnh viện.",
        "我喜欢学习中文。": "Tôi thích học tiếng Trung.",
        "今天我们学习中文。": "Hôm nay chúng ta học tiếng Trung.",
    }

    async def translate_batch(self, texts: list[str], source_language: str, target_language: str) -> list[str]:
        return [self.phrase_map.get(text, f"[vi] {text}") for text in texts]


class OpenAITranslationProvider(TranslationProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.openai_translation_api_key or settings.openai_api_key
        self.model = model or settings.openai_translation_model

    async def translate_batch(self, texts: list[str], source_language: str, target_language: str) -> list[str]:
        if not texts:
            return []
        if not self.api_key:
            raise TranslationProviderError("OPENAI_TRANSLATION_API_KEY is required when TRANSLATION_PROVIDER=openai")

        try:
            return await self._translate_batch_once(texts, source_language, target_language)
        except TranslationProviderError as exc:
            if len(texts) == 1:
                return [self._placeholder_translation(texts[0], target_language)]
            if not self._can_recover_from(exc):
                raise
            return await self._translate_batch_recovering(texts, source_language, target_language)

    async def _translate_batch_once(self, texts: list[str], source_language: str, target_language: str) -> list[str]:
        prompt = (
            "Translate each Chinese subtitle into natural Vietnamese. "
            "Preserve names as names. Return exactly one JSON array of strings with the same length and order as the input. "
            "Do not wrap the JSON in markdown. Do not include explanations, labels, or extra text.\n\n"
            f"Source language: {source_language}\n"
            f"Target language: {target_language}\n"
            f"Subtitles: {json.dumps(texts, ensure_ascii=False)}"
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": prompt,
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TranslationProviderError(f"OpenAI translation request failed: {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise TranslationProviderError("OpenAI translation request failed") from exc

        output_text = self._extract_output_text(response.json())
        translations = self._parse_translation_array(output_text)
        if len(translations) != len(texts):
            raise TranslationProviderError("OpenAI translation response length did not match request")
        return translations

    async def _translate_batch_recovering(self, texts: list[str], source_language: str, target_language: str) -> list[str]:
        if len(texts) == 1:
            try:
                return await self._translate_batch_once(texts, source_language, target_language)
            except TranslationProviderError:
                return [self._placeholder_translation(texts[0], target_language)]

        midpoint = len(texts) // 2
        left = await self._translate_batch_with_recovery(texts[:midpoint], source_language, target_language)
        right = await self._translate_batch_with_recovery(texts[midpoint:], source_language, target_language)
        return [*left, *right]

    async def _translate_batch_with_recovery(self, texts: list[str], source_language: str, target_language: str) -> list[str]:
        try:
            return await self._translate_batch_once(texts, source_language, target_language)
        except TranslationProviderError as exc:
            if self._can_recover_from(exc):
                return await self._translate_batch_recovering(texts, source_language, target_language)
            if len(texts) == 1:
                return [self._placeholder_translation(texts[0], target_language)]
            raise

    def _can_recover_from(self, exc: TranslationProviderError) -> bool:
        return exc.message in {
            "OpenAI translation response length did not match request",
            "OpenAI translation response was not valid JSON",
            "OpenAI translation response must be a JSON array of strings",
            "OpenAI translation response did not include text output",
        }

    def _placeholder_translation(self, text: str, target_language: str) -> str:
        return f"[{target_language}] {text}"

    def _extract_output_text(self, payload: dict) -> str:
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]

        chunks: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        if chunks:
            return "".join(chunks)
        raise TranslationProviderError("OpenAI translation response did not include text output")

    def _parse_translation_array(self, output_text: str) -> list[str]:
        cleaned = self._extract_json_array_text(output_text)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise TranslationProviderError("OpenAI translation response was not valid JSON") from exc
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise TranslationProviderError("OpenAI translation response must be a JSON array of strings")
        return parsed

    def _extract_json_array_text(self, output_text: str) -> str:
        cleaned = output_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        if cleaned.startswith("[") and cleaned.endswith("]"):
            return cleaned

        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1 and start < end:
            return cleaned[start : end + 1]
        return cleaned


class CachedTranslationProvider(TranslationProvider):
    def __init__(self, provider: TranslationProvider, cache: RedisCache) -> None:
        self.provider = provider
        self.cache = cache

    async def translate_batch(self, texts: list[str], source_language: str, target_language: str) -> list[str]:
        digest = hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode("utf-8")).hexdigest()
        key = f"translation:{source_language}-{target_language}:{digest}"
        cached = await self.cache.get(key)
        if cached:
            return list(json.loads(cached))
        translations = await self.provider.translate_batch(texts, source_language, target_language)
        await self.cache.set(key, json.dumps(translations, ensure_ascii=False))
        return translations


def build_translation_provider(cache: RedisCache) -> TranslationProvider:
    provider_name = settings.translation_provider.lower()
    if provider_name == "openai":
        provider: TranslationProvider = OpenAITranslationProvider()
    else:
        provider = LocalTranslationProvider()
    return CachedTranslationProvider(provider, cache)
