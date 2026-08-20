import pytest

from app.services.dictionary_service import LocalDictionaryProvider
from app.services.segmentation_service import JiebaSegmentationProvider
from app.services.subtitle_service import RawSubtitle, SubtitleService
from app.services.translation_service import LocalTranslationProvider


@pytest.mark.asyncio
async def test_process_lines_segments_translates_and_enriches_tokens() -> None:
    service = SubtitleService(
        db=None,  # type: ignore[arg-type]
        cache=None,  # type: ignore[arg-type]
        youtube_service=None,  # type: ignore[arg-type]
        subtitle_provider=None,  # type: ignore[arg-type]
        asr_provider=None,  # type: ignore[arg-type]
        segmentation_provider=JiebaSegmentationProvider(),
        translation_provider=LocalTranslationProvider(),
        dictionary_provider=LocalDictionaryProvider(),
    )

    lines = await service._process_lines([RawSubtitle(12.5, 15.2, "我在医院工作")], "zh", "vi")

    assert lines[0]["translation"] == "Tôi làm việc ở bệnh viện"
    assert [token["text"] for token in lines[0]["tokens"]] == ["我", "在", "医院", "工作"]
    assert lines[0]["tokens"][2]["pinyin"] == "yīyuàn"
