import pytest

from app.schemas.dictionary import DictionaryContext, DictionaryEnrichment
from app.services.dictionary_service import (
    CVDictDictionaryProvider,
    HeuristicDictionaryEnrichmentProvider,
    LearningDictionaryProvider,
    LocalDictionaryProvider,
    OpenAIDictionaryEnrichmentProvider,
    context_hash,
    load_cvdict_index,
)


class FakeCache:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.get_keys: list[str] = []
        self.set_keys: list[str] = []

    async def get(self, key: str) -> str | None:
        self.get_keys.append(key)
        return self.values.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self.set_keys.append(key)
        self.values[key] = value


class BrokenCache(FakeCache):
    async def get(self, key: str) -> str | None:
        raise RuntimeError("redis down")

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        raise RuntimeError("redis down")


class ChineseExplanationEnrichmentProvider:
    async def enrich(self, entry, context, source_language, target_language) -> DictionaryEnrichment:
        return DictionaryEnrichment(
            context=DictionaryContext(
                original_sentence=context,
                selected_meaning="vượt trội về hương vị",
                phrase="超好喝",
                phrase_pinyin="chāo hǎo hē",
                phrase_meaning="rất ngon",
                explanation="这个词常用于描述饮料味道很好，超过预期。",
            )
        )


@pytest.mark.asyncio
async def test_basic_lookup_returns_structured_meanings(tmp_path) -> None:
    dictionary_file = tmp_path / "CVDICT.u8"
    dictionary_file.write_text("字幕 字幕 [zi4 mu4] /phụ đề/chú thích/\n", encoding="utf-8")
    load_cvdict_index.cache_clear()

    entry = await CVDictDictionaryProvider(path=str(dictionary_file)).lookup("字幕")

    assert entry.word == "字幕"
    assert entry.pinyin == "zìmù"
    assert entry.meanings[0].meaning == "phụ đề"
    assert entry.meanings[1].meaning == "chú thích"
    assert entry.meaning == "phụ đề; chú thích"


@pytest.mark.asyncio
async def test_contextual_phrase_detects_calling_meaning() -> None:
    entry = await LearningDictionaryProvider(
        LocalDictionaryProvider(),
        HeuristicDictionaryEnrichmentProvider(),
        FakeCache(),  # type: ignore[arg-type]
    ).lookup("打", "我给妈妈打电话。")

    assert entry.context is not None
    assert entry.context.phrase == "打电话"
    assert "gọi điện" in (entry.context.phrase_meaning or "")


@pytest.mark.asyncio
async def test_contextual_cache_keys_are_separated() -> None:
    cache = FakeCache()
    provider = LearningDictionaryProvider(LocalDictionaryProvider(), HeuristicDictionaryEnrichmentProvider(), cache)  # type: ignore[arg-type]

    await provider.lookup("打", "我给妈妈打电话。")
    await provider.lookup("打", "他打篮球。")

    assert f"dictionary:context:v5:zh-vi:打:{context_hash('打', '我给妈妈打电话。')}" in cache.set_keys
    assert f"dictionary:context:v5:zh-vi:打:{context_hash('打', '他打篮球。')}" in cache.set_keys
    assert context_hash("打", "我给妈妈打电话。") != context_hash("打", "他打篮球。")


@pytest.mark.asyncio
async def test_redis_failure_does_not_break_lookup() -> None:
    entry = await LearningDictionaryProvider(
        LocalDictionaryProvider(),
        HeuristicDictionaryEnrichmentProvider(),
        BrokenCache(),  # type: ignore[arg-type]
    ).lookup("字幕", "字幕提供者-SnoW°笨兔")

    assert entry.word == "字幕"
    assert entry.meaning


@pytest.mark.asyncio
async def test_chinese_explanation_is_replaced_with_vietnamese() -> None:
    entry = await LearningDictionaryProvider(
        LocalDictionaryProvider(),
        ChineseExplanationEnrichmentProvider(),  # type: ignore[arg-type]
        FakeCache(),  # type: ignore[arg-type]
    ).lookup("超好喝", "这杯奶茶超好喝。")

    assert entry.context is not None
    assert entry.context.explanation is not None
    assert "Giải thích" not in entry.context.explanation
    assert "Trong ngữ cảnh này" in entry.context.explanation


class MalformedResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"output_text": '{"collocations": "bad"}'}


class MalformedAsyncClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "MalformedAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, headers: dict, json: dict) -> MalformedResponse:
        return MalformedResponse()


@pytest.mark.asyncio
async def test_malformed_ai_enrichment_does_not_crash(monkeypatch) -> None:
    monkeypatch.setattr("app.services.dictionary_service.httpx.AsyncClient", MalformedAsyncClient)
    basic = await LocalDictionaryProvider().lookup("字幕")

    enrichment = await OpenAIDictionaryEnrichmentProvider(api_key="test-key").enrich(basic, "字幕提供者-SnoW°笨兔", "zh", "vi")

    assert isinstance(enrichment.collocations, list)
