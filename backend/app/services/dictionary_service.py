import hashlib
import logging
import re
import json
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

import httpx
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.redis import RedisCache
from app.models import DictionaryEnrichmentCache
from app.schemas.dictionary import DictionaryCollocation, DictionaryContext, DictionaryEnrichment, DictionaryEntry, DictionaryExample, DictionaryMeaning

logger = logging.getLogger(__name__)

CVDICT_LINE_PATTERN = re.compile(r"^(?P<traditional>\S+)\s+(?P<simplified>\S+)\s+\[(?P<pinyin>[^\]]+)\]\s+/(?P<meaning>.+)/$")
TONE_MARKS = {
    "a": "āáǎàa",
    "e": "ēéěèe",
    "i": "īíǐìi",
    "o": "ōóǒòo",
    "u": "ūúǔùu",
    "ü": "ǖǘǚǜü",
}


class DictionaryProvider(ABC):
    @abstractmethod
    async def lookup(self, word: str, context: str | None = None) -> DictionaryEntry:
        raise NotImplementedError


class LocalDictionaryProvider(DictionaryProvider):
    entries = {
        "我": ("wǒ", ["tôi"], "đại từ"),
        "今天": ("jīntiān", ["hôm nay"], "danh từ"),
        "在": ("zài", ["ở", "tại"], "giới từ"),
        "医院": ("yīyuàn", ["bệnh viện"], "danh từ"),
        "工作": ("gōngzuò", ["làm việc", "công việc"], "động từ / danh từ"),
        "学习": ("xuéxí", ["học tập"], "động từ"),
        "中文": ("zhōngwén", ["tiếng Trung"], "danh từ"),
        "喜欢": ("xǐhuan", ["thích"], "động từ"),
        "字幕": ("zìmù", ["phụ đề", "chú thích"], "danh từ"),
        "打": ("dǎ", ["đánh", "gọi", "chơi", "mở / thực hiện"], "động từ"),
        "开": ("kāi", ["mở", "lái", "bắt đầu"], "động từ"),
        "看": ("kàn", ["nhìn", "xem", "đọc"], "động từ"),
        "水果": ("shuǐguǒ", ["trái cây"], "danh từ"),
    }

    async def lookup(self, word: str, context: str | None = None) -> DictionaryEntry:
        pinyin, meanings, part_of_speech = self.entries.get(word, (self._to_pinyin(word), ["Tra cứu cần nhà cung cấp từ điển"], None))
        return build_dictionary_entry(
            word=word,
            pinyin=pinyin,
            meanings=[DictionaryMeaning(meaning=item) for item in meanings],
            part_of_speech=part_of_speech,
            context=basic_context_for(word, pinyin, meanings, context),
        )

    def _to_pinyin(self, word: str) -> str:
        try:
            from pypinyin import lazy_pinyin, Style

            return format_headword_pinyin(word, " ".join(lazy_pinyin(word, style=Style.TONE)))
        except Exception:
            return ""


class CVDictDictionaryProvider(DictionaryProvider):
    def __init__(self, path: str | None = None, fallback: DictionaryProvider | None = None) -> None:
        self.path = path or settings.cvdict_path
        self.fallback = fallback or LocalDictionaryProvider()

    async def lookup(self, word: str, context: str | None = None) -> DictionaryEntry:
        index = load_cvdict_index(self.path)
        entries = index.get(word)
        if not entries:
            return await self.fallback.lookup(word, context)

        first = entries[0]
        pinyin = format_headword_pinyin(word, numbered_pinyin_to_marks(first["pinyin"]))
        part_of_speech = None
        meanings = cvdict_meanings(entries)
        local_entry = LocalDictionaryProvider.entries.get(word)
        if local_entry:
            pinyin = local_entry[0]
            part_of_speech = local_entry[2]
            meanings = merge_meanings([DictionaryMeaning(meaning=item, definition=definition_for_meaning(item)) for item in local_entry[1]], meanings)
        return build_dictionary_entry(
            word=word,
            pinyin=pinyin,
            meanings=meanings,
            part_of_speech=part_of_speech,
            context=basic_context_for(word, pinyin, [item.meaning for item in meanings], context),
        )


class CachedDictionaryProvider(DictionaryProvider):
    def __init__(
        self,
        provider: DictionaryProvider,
        cache: RedisCache,
        source_language: str = "zh",
        target_language: str = "vi",
        provider_name: str = "local",
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.source_language = source_language
        self.target_language = target_language
        self.provider_name = provider_name

    async def lookup(self, word: str, context: str | None = None) -> DictionaryEntry:
        key = f"dictionary:basic:{self.provider_name}:{self.source_language}-{self.target_language}:{word}"
        cached = await safe_cache_get(self.cache, key)
        if cached:
            return DictionaryEntry.model_validate_json(cached)
        entry = await self.provider.lookup(word, None)
        await safe_cache_set(self.cache, key, entry.model_dump_json())
        return entry


class DictionaryEnrichmentProvider(ABC):
    @abstractmethod
    async def enrich(self, entry: DictionaryEntry, context: str | None, source_language: str, target_language: str) -> DictionaryEnrichment:
        raise NotImplementedError


class HeuristicDictionaryEnrichmentProvider(DictionaryEnrichmentProvider):
    common_collocations = {
        "字幕": [
            DictionaryCollocation(text="中文字幕", pinyin="zhōngwén zìmù", meaning="phụ đề tiếng Trung"),
            DictionaryCollocation(text="英文字幕", pinyin="yīngwén zìmù", meaning="phụ đề tiếng Anh"),
            DictionaryCollocation(text="打开字幕", pinyin="dǎkāi zìmù", meaning="bật phụ đề"),
            DictionaryCollocation(text="关闭字幕", pinyin="guānbì zìmù", meaning="tắt phụ đề"),
            DictionaryCollocation(text="添加字幕", pinyin="tiānjiā zìmù", meaning="thêm phụ đề"),
        ],
        "打": [
            DictionaryCollocation(text="打电话", pinyin="dǎ diànhuà", meaning="gọi điện"),
            DictionaryCollocation(text="打篮球", pinyin="dǎ lánqiú", meaning="chơi bóng rổ"),
            DictionaryCollocation(text="打人", pinyin="dǎ rén", meaning="đánh người"),
            DictionaryCollocation(text="打开", pinyin="dǎkāi", meaning="mở ra"),
        ],
    }
    examples = {
        "字幕": [
            DictionaryExample(chinese="这个视频有中文字幕。", pinyin="Zhège shìpín yǒu Zhōngwén zìmù.", vietnamese="Video này có phụ đề tiếng Trung."),
            DictionaryExample(chinese="请打开字幕。", pinyin="Qǐng dǎkāi zìmù.", vietnamese="Hãy bật phụ đề."),
        ],
        "打": [
            DictionaryExample(chinese="我给妈妈打电话。", pinyin="Wǒ gěi māma dǎ diànhuà.", vietnamese="Tôi gọi điện cho mẹ."),
            DictionaryExample(chinese="他喜欢打篮球。", pinyin="Tā xǐhuan dǎ lánqiú.", vietnamese="Anh ấy thích chơi bóng rổ."),
        ],
    }

    async def enrich(self, entry: DictionaryEntry, context: str | None, source_language: str, target_language: str) -> DictionaryEnrichment:
        phrase_context = phrase_context_for(entry.word, context)
        return DictionaryEnrichment(
            part_of_speech=entry.part_of_speech,
            context=phrase_context,
            collocations=self.common_collocations.get(entry.word, [])[:5],
            examples=self.examples.get(entry.word, [])[:2],
        )


class OpenAIDictionaryEnrichmentProvider(DictionaryEnrichmentProvider):
    def __init__(self, fallback: DictionaryEnrichmentProvider | None = None, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_translation_model
        self.fallback = fallback or HeuristicDictionaryEnrichmentProvider()

    async def enrich(self, entry: DictionaryEntry, context: str | None, source_language: str, target_language: str) -> DictionaryEnrichment:
        fallback = await self.fallback.enrich(entry, context, source_language, target_language)
        if not self.api_key:
            return fallback

        prompt = (
            "You enrich a Chinese-Vietnamese dictionary entry for language learners. "
            "Use natural modern Mandarin only. Do not invent rare meanings, grammar labels, or unnatural collocations. "
            "All learner-facing prose must be written in Vietnamese: part_of_speech, selected_meaning, phrase_meaning, explanation, collocation meanings, and example Vietnamese. "
            "The Chinese fields may contain Chinese, but explanations must not be written as Chinese sentences. "
            "If the context looks like a proper noun or place name and you cannot verify it from the given dictionary meanings, say in Vietnamese that it appears to be a proper name in the subtitle; do not invent location facts. "
            "Do not replace verified dictionary meanings. Return only JSON matching this shape: "
            '{"part_of_speech": string|null, "context": {"selected_meaning": string|null, "phrase": string|null, '
            '"phrase_pinyin": string|null, "phrase_meaning": string|null, "explanation": string|null}|null, '
            '"collocations": [{"text": string, "pinyin": string, "meaning": string}], '
            '"examples": [{"chinese": string, "pinyin": string, "vietnamese": string}]}. '
            "Return 3-5 collocations and 2 short examples when possible.\n\n"
            f"Input: {json.dumps({'word': entry.word, 'pinyin': entry.pinyin, 'dictionary_meanings': [item.meaning for item in entry.meanings], 'context': context, 'source_language': source_language, 'target_language': target_language}, ensure_ascii=False)}"
        )
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/responses",
                        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                        json={"model": self.model, "input": prompt, "temperature": 0.1},
                    )
                response.raise_for_status()
                enrichment = DictionaryEnrichment.model_validate_json(extract_json_object_text(extract_output_text(response.json())))
                return merge_enrichment(fallback, enrichment)
            except (httpx.HTTPError, ValidationError, ValueError) as exc:
                last_error = exc
        logger.warning("Dictionary OpenAI enrichment failed for %s: %s", entry.word, last_error)
        return fallback


class LearningDictionaryProvider(DictionaryProvider):
    def __init__(
        self,
        basic_provider: DictionaryProvider,
        enrichment_provider: DictionaryEnrichmentProvider,
        cache: RedisCache,
        db: AsyncSession | None = None,
        source_language: str = "zh",
        target_language: str = "vi",
    ) -> None:
        self.basic_provider = basic_provider
        self.enrichment_provider = enrichment_provider
        self.cache = cache
        self.db = db
        self.source_language = source_language
        self.target_language = target_language
        self.model = getattr(enrichment_provider, "model", enrichment_provider.__class__.__name__)

    async def lookup(self, word: str, context: str | None = None) -> DictionaryEntry:
        entry = await self.basic_provider.lookup(word, None)
        if not context:
            return entry

        context_key = f"dictionary:context:v5:{self.source_language}-{self.target_language}:{word}:{context_hash(word, context)}"
        cached = await safe_cache_get(self.cache, context_key)
        if cached:
            return apply_enrichment(entry, DictionaryEnrichment.model_validate_json(cached), context)

        persisted = await safe_db_get_enrichment(
            self.db,
            word,
            context_hash(word, context),
            self.source_language,
            self.target_language,
        )
        if persisted is not None:
            await safe_cache_set(self.cache, context_key, persisted.model_dump_json())
            return apply_enrichment(entry, persisted, context)

        try:
            enrichment = await self.enrichment_provider.enrich(entry, context, self.source_language, self.target_language)
            await safe_cache_set(self.cache, context_key, enrichment.model_dump_json())
            await safe_db_set_enrichment(
                self.db,
                word,
                context,
                context_hash(word, context),
                self.source_language,
                self.target_language,
                self.model,
                enrichment,
            )
            return apply_enrichment(entry, enrichment, context)
        except Exception as exc:
            logger.warning("Dictionary enrichment failed for %s: %s", word, exc)
            return entry.model_copy(update={"enrichment_error": "Không thể tải thêm giải thích."})


def build_dictionary_provider(cache: RedisCache, enrich: bool = False, db: AsyncSession | None = None) -> DictionaryProvider:
    provider_name = settings.dictionary_provider.lower()
    if provider_name == "cvdict":
        provider: DictionaryProvider = CVDictDictionaryProvider()
    else:
        provider = LocalDictionaryProvider()
    cache_provider_name = "cvdict:v3" if provider_name == "cvdict" else provider_name
    basic_provider = CachedDictionaryProvider(provider, cache, provider_name=cache_provider_name)
    if not enrich:
        return basic_provider
    return LearningDictionaryProvider(
        basic_provider,
        enrichment_provider=OpenAIDictionaryEnrichmentProvider(),
        cache=cache,
        db=db,
    )


@lru_cache(maxsize=2)
def load_cvdict_index(path: str) -> dict[str, list[dict[str, str]]]:
    dictionary_path = Path(path)
    if not dictionary_path.exists():
        logger.warning("CVDICT file not found at %s; dictionary falls back to local entries", dictionary_path)
        return {}

    index: dict[str, list[dict[str, str]]] = {}
    with dictionary_path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = CVDICT_LINE_PATTERN.match(line)
            if not match:
                continue
            traditional = match.group("traditional")
            simplified = match.group("simplified")
            entry = {
                "traditional": traditional,
                "simplified": simplified,
                "pinyin": match.group("pinyin"),
                "meaning": clean_cvdict_meaning(match.group("meaning")),
            }
            index.setdefault(simplified, []).append(entry)
            if traditional != simplified:
                index.setdefault(traditional, []).append(entry)
    logger.info("Loaded CVDICT entries", extra={"path": str(dictionary_path), "entry_count": len(index)})
    return index


def numbered_pinyin_to_marks(text: str) -> str:
    return " ".join(_convert_pinyin_syllable(syllable) for syllable in text.replace("u:", "ü").split())


def clean_cvdict_meaning(text: str) -> str:
    parts = []
    for part in text.split("/"):
        cleaned = part.strip()
        if not cleaned or cleaned.startswith("LT:"):
            continue
        parts.append(cleaned)
    return "; ".join(parts)


def cvdict_meanings(entries: list[dict[str, str]]) -> list[DictionaryMeaning]:
    seen: dict[str, DictionaryMeaning] = {}
    for entry in entries[:6]:
        for meaning in split_meaning_text(entry["meaning"]):
            if meaning and meaning not in seen:
                seen[meaning] = DictionaryMeaning(meaning=meaning, definition=definition_for_meaning(meaning))
    return list(seen.values())[:6] or [DictionaryMeaning(meaning="Chưa có nghĩa tiếng Việt.")]


def merge_meanings(primary: list[DictionaryMeaning], secondary: list[DictionaryMeaning]) -> list[DictionaryMeaning]:
    merged: dict[str, DictionaryMeaning] = {}
    for item in [*primary, *secondary]:
        if item.meaning and item.meaning not in merged:
            merged[item.meaning] = item
    return list(merged.values())[:6]


def split_meaning_text(text: str) -> list[str]:
    parts: list[str] = []
    for part in re.split(r";|；", text):
        cleaned = part.strip()
        if cleaned:
            parts.append(cleaned)
    return parts


def definition_for_meaning(meaning: str) -> str | None:
    lowered = meaning.lower()
    if "phụ đề" in lowered:
        return "Phần chữ hiển thị trên video, phim hoặc chương trình để thể hiện lời thoại."
    if "chú thích" in lowered:
        return "Nội dung chữ được hiển thị để giải thích hoặc bổ sung thông tin."
    if "bệnh viện" in lowered:
        return "Nơi khám, điều trị và chăm sóc sức khỏe cho người bệnh."
    if "làm việc" in lowered:
        return "Thực hiện công việc hoặc nhiệm vụ."
    if "trái cây" in lowered:
        return "Nhóm quả ăn được, thường có vị ngọt hoặc chua."
    return None


def build_dictionary_entry(
    word: str,
    pinyin: str | None,
    meanings: list[DictionaryMeaning],
    part_of_speech: str | None = None,
    context: DictionaryContext | None = None,
    collocations: list[DictionaryCollocation] | None = None,
    examples: list[DictionaryExample] | None = None,
    enrichment_error: str | None = None,
) -> DictionaryEntry:
    meaning_text = "; ".join(item.meaning for item in meanings) if meanings else "Chưa có nghĩa tiếng Việt."
    example = examples[0] if examples else None
    return DictionaryEntry(
        word=word,
        pinyin=pinyin,
        meaning=meaning_text,
        part_of_speech=part_of_speech,
        contextual_meaning=context.phrase_meaning or context.selected_meaning if context else None,
        example_zh=context.original_sentence if context else example.chinese if example else None,
        example_vi=example.vietnamese if example else None,
        meanings=meanings,
        context=context,
        collocations=collocations or [],
        examples=examples or [],
        enrichment_error=enrichment_error,
    )


def apply_enrichment(entry: DictionaryEntry, enrichment: DictionaryEnrichment, original_sentence: str | None) -> DictionaryEntry:
    context = sanitize_context(entry.word, enrichment.context)
    if context and not context.original_sentence:
        context = context.model_copy(update={"original_sentence": original_sentence})
    return build_dictionary_entry(
        word=entry.word,
        pinyin=entry.pinyin,
        meanings=entry.meanings or [DictionaryMeaning(meaning=entry.meaning)],
        part_of_speech=enrichment.part_of_speech or entry.part_of_speech,
        context=context,
        collocations=enrichment.collocations,
        examples=enrichment.examples,
        enrichment_error=None,
    )


def merge_enrichment(fallback: DictionaryEnrichment, enrichment: DictionaryEnrichment) -> DictionaryEnrichment:
    context = sanitize_context("", enrichment.context or fallback.context)
    if fallback.context and fallback.context.phrase:
        context = DictionaryContext(
            original_sentence=enrichment.context.original_sentence if enrichment.context and enrichment.context.original_sentence else fallback.context.original_sentence,
            selected_meaning=fallback.context.phrase_meaning or fallback.context.selected_meaning,
            phrase=fallback.context.phrase,
            phrase_pinyin=fallback.context.phrase_pinyin,
            phrase_meaning=fallback.context.phrase_meaning,
            explanation=fallback.context.explanation,
        )
    examples = enrichment.examples or fallback.examples
    if context and context.phrase:
        phrase_examples = [example for example in examples if context.phrase in example.chinese]
        fallback_phrase_examples = [example for example in fallback.examples if context.phrase in example.chinese]
        examples = phrase_examples[:2] if phrase_examples else fallback_phrase_examples[:2]
    return DictionaryEnrichment(
        part_of_speech=normalize_part_of_speech(enrichment.part_of_speech or fallback.part_of_speech),
        context=context,
        collocations=enrichment.collocations or fallback.collocations,
        examples=examples,
    )


def basic_context_for(word: str, pinyin: str | None, meanings: list[str], context: str | None) -> DictionaryContext | None:
    if not context:
        return None
    phrase_context = phrase_context_for(word, context)
    if phrase_context:
        return phrase_context
    selected = meanings[0] if meanings else None
    return DictionaryContext(
        original_sentence=context,
        selected_meaning=selected,
        explanation=f"Trong câu này, {word} mang nghĩa {selected}." if selected else None,
    )


def sanitize_context(word: str, context: DictionaryContext | None) -> DictionaryContext | None:
    if not context:
        return None
    if context.explanation and explanation_has_chinese_sentence(context.explanation, word, context.phrase):
        phrase = context.phrase or word
        meaning = context.phrase_meaning or context.selected_meaning
        explanation = (
            f"Trong ngữ cảnh này, {phrase} được dùng với nghĩa \"{meaning}\"."
            if meaning
            else f"Trong ngữ cảnh này, {phrase} có vẻ là một tên riêng hoặc cụm danh từ trong phụ đề."
        )
        return context.model_copy(update={"explanation": explanation})
    return context


def explanation_has_chinese_sentence(explanation: str, word: str, phrase: str | None) -> bool:
    allowed = {word, phrase or ""}
    normalized = explanation
    for item in allowed:
        if item:
            normalized = normalized.replace(item, "")
    han_chars = re.findall(r"[\u3400-\u9fff]", normalized)
    return len(han_chars) >= 4


def phrase_context_for(word: str, context: str | None) -> DictionaryContext | None:
    if not context:
        return None
    phrase_map = {
        "字幕": [
            ("字幕提供者", "zìmù tígōngzhě", "người cung cấp phụ đề", 'Trong cụm này, 字幕 mang nghĩa "phụ đề".'),
            ("中文字幕", "zhōngwén zìmù", "phụ đề tiếng Trung", 'Trong cụm này, 字幕 mang nghĩa "phụ đề".'),
            ("英文字幕", "yīngwén zìmù", "phụ đề tiếng Anh", 'Trong cụm này, 字幕 mang nghĩa "phụ đề".'),
        ],
        "打": [
            ("打电话", "dǎ diànhuà", "gọi điện", 'Trong câu này, 打 được dùng trong cụm 打电话, nghĩa là "gọi điện".'),
            ("打篮球", "dǎ lánqiú", "chơi bóng rổ", 'Trong câu này, 打 được dùng trong cụm 打篮球, nghĩa là "chơi bóng rổ".'),
            ("打人", "dǎ rén", "đánh người", 'Trong câu này, 打 mang nghĩa "đánh".'),
        ],
        "开": [
            ("打开", "dǎkāi", "mở ra", 'Trong cụm này, 开 liên quan đến hành động mở.'),
        ],
    }
    for phrase, phrase_pinyin, phrase_meaning, explanation in phrase_map.get(word, []):
        if phrase in context:
            return DictionaryContext(
                original_sentence=context,
                selected_meaning=phrase_meaning,
                phrase=phrase,
                phrase_pinyin=phrase_pinyin,
                phrase_meaning=phrase_meaning,
                explanation=explanation,
            )
    return None


def context_hash(word: str, context: str) -> str:
    normalized = re.sub(r"\s+", " ", context).strip()
    return hashlib.sha256(f"{word}\n{normalized}".encode("utf-8")).hexdigest()[:24]


def normalize_part_of_speech(value: str | None) -> str | None:
    if not value:
        return value
    mapping = {
        "noun": "danh từ",
        "名词": "danh từ",
        "verb": "động từ",
        "动词": "động từ",
        "adjective": "tính từ",
        "形容词": "tính từ",
        "adverb": "trạng từ",
        "副词": "trạng từ",
        "pronoun": "đại từ",
        "代词": "đại từ",
        "preposition": "giới từ",
        "介词": "giới từ",
    }
    lowered = value.strip().lower()
    return mapping.get(lowered, mapping.get(value.strip(), value.strip()))


async def safe_cache_get(cache: RedisCache, key: str) -> str | None:
    try:
        return await cache.get(key)
    except Exception as exc:
        logger.warning("Dictionary cache get failed for %s: %s", key, exc)
        return None


async def safe_cache_set(cache: RedisCache, key: str, value: str) -> None:
    try:
        await cache.set(key, value)
    except Exception as exc:
        logger.warning("Dictionary cache set failed for %s: %s", key, exc)


async def safe_db_get_enrichment(
    db: AsyncSession | None,
    word: str,
    lookup_context_hash: str,
    source_language: str,
    target_language: str,
) -> DictionaryEnrichment | None:
    if db is None:
        return None
    try:
        result = await db.execute(
            select(DictionaryEnrichmentCache).where(
                DictionaryEnrichmentCache.word == word,
                DictionaryEnrichmentCache.context_hash == lookup_context_hash,
                DictionaryEnrichmentCache.source_language == source_language,
                DictionaryEnrichmentCache.target_language == target_language,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return DictionaryEnrichment.model_validate(record.enrichment_json)
    except (ValidationError, ValueError) as exc:
        logger.warning("Dictionary SQL enrichment is invalid for %s: %s", word, exc)
        return None
    except Exception as exc:
        await db.rollback()
        logger.warning("Dictionary SQL cache get failed for %s: %s", word, exc)
        return None


async def safe_db_set_enrichment(
    db: AsyncSession | None,
    word: str,
    context: str,
    lookup_context_hash: str,
    source_language: str,
    target_language: str,
    model: str,
    enrichment: DictionaryEnrichment,
) -> None:
    if db is None:
        return
    try:
        statement = insert(DictionaryEnrichmentCache).values(
            word=word,
            context_hash=lookup_context_hash,
            context=re.sub(r"\s+", " ", context).strip()[:4000],
            source_language=source_language,
            target_language=target_language,
            model=model,
            enrichment_json=enrichment.model_dump(mode="json"),
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_dictionary_enrichment_lookup",
            set_={
                "context": statement.excluded.context,
                "model": statement.excluded.model,
                "enrichment_json": statement.excluded.enrichment_json,
                "updated_at": func.now(),
            },
        )
        await db.execute(statement)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.warning("Dictionary SQL cache set failed for %s: %s", word, exc)


def format_headword_pinyin(word: str, pinyin: str | None) -> str | None:
    if not pinyin:
        return pinyin
    syllables = pinyin.split()
    if len(word) > 1 and len(syllables) == len(word):
        return "".join(syllables)
    return pinyin


def extract_output_text(payload: dict) -> str:
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
    raise ValueError("OpenAI dictionary response did not include text output")


def extract_json_object_text(output_text: str) -> str:
    cleaned = output_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and start < end:
        return cleaned[start : end + 1]
    return cleaned


def _convert_pinyin_syllable(syllable: str) -> str:
    match = re.match(r"^(.+?)([1-5])$", syllable)
    if not match:
        return syllable
    base = match.group(1)
    tone = int(match.group(2))
    if tone == 5:
        return base

    target_index = _tone_vowel_index(base)
    if target_index is None:
        return base
    vowel = base[target_index]
    marked = TONE_MARKS.get(vowel.lower(), vowel)[tone - 1]
    if vowel.isupper():
        marked = marked.upper()
    return f"{base[:target_index]}{marked}{base[target_index + 1:]}"


def _tone_vowel_index(syllable: str) -> int | None:
    lower = syllable.lower()
    for preferred in ("a", "e"):
        index = lower.find(preferred)
        if index >= 0:
            return index
    ou_index = lower.find("ou")
    if ou_index >= 0:
        return ou_index
    indexes = [index for index, char in enumerate(lower) if char in "aeiouü"]
    return indexes[-1] if indexes else None
