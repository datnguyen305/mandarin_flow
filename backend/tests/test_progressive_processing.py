import pytest

from app.core.config import settings
from app.services.segmentation_service import SegmentationProvider
from app.services.subtitle_queue import format_sse, prioritized_batch_order
from app.services.subtitle_service import SubtitleService
from app.services.transcript_types import RawSubtitle
from app.services.translation_service import TranslationProvider
from app.schemas.dictionary import DictionaryEntry


class FakeSegmentationProvider(SegmentationProvider):
    def segment(self, text: str) -> list[str]:
        if text == "我今天去医院工作":
            return ["我", "今天", "去", "医院", "工作"]
        return [text]


class CountingTranslationProvider(TranslationProvider):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def translate_batch(self, texts: list[str], source_language: str, target_language: str) -> list[str]:
        self.calls.append(texts)
        return [f"vi:{text}" for text in texts]


class PlaceholderTranslationProvider(TranslationProvider):
    async def translate_batch(self, texts: list[str], source_language: str, target_language: str) -> list[str]:
        return [f"[{target_language}] {text}" for text in texts]


class FakeDictionaryProvider:
    meanings = {
        "我": ("wǒ", "tôi"),
        "今天": ("jīntiān", "hôm nay"),
        "去": ("qù", "đi"),
        "医院": ("yīyuàn", "bệnh viện"),
        "工作": ("gōngzuò", "làm việc"),
    }

    async def lookup(self, word: str, context: str | None = None) -> DictionaryEntry:
        pinyin, meaning = self.meanings.get(word, ("", ""))
        return DictionaryEntry(word=word, pinyin=pinyin, meaning=meaning)


class FakeSubtitle:
    def __init__(self, sequence_number: int, start: float, end: float, text: str) -> None:
        self.id = sequence_number + 1
        self.sequence_number = sequence_number
        self.start_time = start
        self.end_time = end
        self.text = text
        self.translated_text = None
        self.processing_status = "raw"
        self.tokens = []


def build_service() -> SubtitleService:
    service = SubtitleService(
        db=None,  # type: ignore[arg-type]
        cache=None,  # type: ignore[arg-type]
        youtube_service=None,  # type: ignore[arg-type]
        subtitle_provider=None,  # type: ignore[arg-type]
        asr_provider=None,  # type: ignore[arg-type]
        segmentation_provider=FakeSegmentationProvider(),
        translation_provider=CountingTranslationProvider(),
        dictionary_provider=None,  # type: ignore[arg-type]
    )
    return service


def build_service_with_dictionary() -> SubtitleService:
    service = SubtitleService(
        db=None,  # type: ignore[arg-type]
        cache=None,  # type: ignore[arg-type]
        youtube_service=None,  # type: ignore[arg-type]
        subtitle_provider=None,  # type: ignore[arg-type]
        asr_provider=None,  # type: ignore[arg-type]
        segmentation_provider=FakeSegmentationProvider(),
        translation_provider=PlaceholderTranslationProvider(),
        dictionary_provider=FakeDictionaryProvider(),  # type: ignore[arg-type]
    )
    return service


def test_batch_creation_uses_time_windows(monkeypatch) -> None:
    monkeypatch.setattr(settings, "subtitle_batch_seconds", 120)
    service = build_service()

    lines = service._raw_lines_with_batches(
        [
            RawSubtitle(start=0, end=2, text="一"),
            RawSubtitle(start=119.9, end=121, text="二"),
            RawSubtitle(start=120, end=122, text="三"),
            RawSubtitle(start=240, end=242, text="四"),
        ]
    )
    batches = service._batch_definitions(lines)

    assert [line["batch_index"] for line in lines] == [0, 0, 1, 2]
    assert [batch["batch_index"] for batch in batches] == [0, 1, 2]
    assert batches[0]["start_time"] == 0
    assert batches[1]["start_time"] == 120


def test_priority_order_after_user_seeks_to_batch_8() -> None:
    pending = set(range(10)) - {3}
    order = prioritized_batch_order(pending, [8, 9, 10])

    assert order[:2] == [8, 9]
    assert 3 not in order
    assert sorted(order) == sorted(pending)


def test_failed_batch_isolation_allows_later_pending_batches() -> None:
    failed_batch = 4
    pending = {5, 6}

    order = prioritized_batch_order(pending, [failed_batch])

    assert order == [5, 6]


@pytest.mark.asyncio
async def test_translation_operates_on_subtitle_batch() -> None:
    service = build_service()
    provider = service.translation_provider
    subtitles = [
        FakeSubtitle(0, 0, 2, "我今天去医院工作"),
        FakeSubtitle(1, 3, 5, "医院离我家很近"),
    ]

    processed = await service._process_subtitle_batch(subtitles, "zh", "vi")  # type: ignore[arg-type]

    assert len(processed) == 2
    assert provider.calls == [["我今天去医院工作", "医院离我家很近"]]  # type: ignore[attr-defined]
    assert [token["text"] for token in processed[0]["tokens"]] == ["我", "今天", "去", "医院", "工作"]
    assert all("meaning" in token and token["meaning"] is None for token in processed[0]["tokens"])


@pytest.mark.asyncio
async def test_batch_processing_uses_token_meanings_when_translation_is_placeholder() -> None:
    service = build_service_with_dictionary()
    subtitles = [FakeSubtitle(0, 0, 2, "我今天去医院工作")]

    processed = await service._process_subtitle_batch(subtitles, "zh", "vi")  # type: ignore[arg-type]

    assert processed[0]["translation"] == "tôi / hôm nay / đi / bệnh viện / làm việc"
    assert processed[0]["tokens"][3]["meaning"] == "bệnh viện"


def test_sse_event_generation() -> None:
    event = format_sse("subtitle_batch", {"video_id": "abc123abc12", "batch_index": 0}, "event-1")

    assert event.startswith("id: event-1\nevent: subtitle_batch\n")
    assert '"batch_index": 0' in event
    assert event.endswith("\n\n")
