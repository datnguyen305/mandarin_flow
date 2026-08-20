from app.services.segmentation_service import JiebaSegmentationProvider, locate_tokens


def test_segmentation_returns_clickable_words() -> None:
    provider = JiebaSegmentationProvider()
    tokens = provider.segment("我今天在医院工作")
    assert "医院" in tokens
    assert "工作" in tokens


def test_locate_tokens_preserves_offsets() -> None:
    located = locate_tokens("我在医院工作", ["我", "在", "医院", "工作"])
    assert located == [
        {"text": "我", "start_index": 0, "end_index": 1},
        {"text": "在", "start_index": 1, "end_index": 2},
        {"text": "医院", "start_index": 2, "end_index": 4},
        {"text": "工作", "start_index": 4, "end_index": 6},
    ]


def test_segmentation_skips_punctuation_tokens() -> None:
    provider = JiebaSegmentationProvider()

    tokens = provider.segment("我在医院工作，今天很好。")

    assert "，" not in tokens
    assert "。" not in tokens
    assert "医院" in tokens
