import pytest

from app.services.vocabulary_service import VocabularyService


class FakeDb:
    async def commit(self) -> None:
        return None


class FakeVideo:
    id = 10
    youtube_video_id = "abc123abc12"
    title = "Demo"


class FakeSubtitle:
    id = 20
    video_id = 10
    text = "我在医院工作"


class FakeSavedItem:
    id = 1
    word = "医院"
    pinyin = "yīyuàn"
    meaning = "bệnh viện"
    timestamp = 12.5
    created_at = "2026-08-18T00:00:00"
    video = FakeVideo()
    subtitle = FakeSubtitle()


class FakeVocabularyRepository:
    async def find_video_and_subtitle(self, youtube_video_id: str, subtitle_id: int) -> tuple[FakeVideo, FakeSubtitle]:
        return FakeVideo(), FakeSubtitle()

    async def save(self, *args) -> FakeSavedItem:
        return FakeSavedItem()

    async def list_for_user(self, user_id: int) -> list[FakeSavedItem]:
        return [FakeSavedItem()]


@pytest.mark.asyncio
async def test_save_and_retrieve_vocabulary() -> None:
    service = VocabularyService(FakeDb())  # type: ignore[arg-type]
    service.repo = FakeVocabularyRepository()  # type: ignore[assignment]

    saved_id = await service.save(1, "医院", "yīyuàn", "bệnh viện", "abc123abc12", 20, 12.5)
    items = await service.list_for_user(1)

    assert saved_id > 0
    assert len(items) == 1
    assert items[0].word == "医院"
    assert items[0].subtitle_sentence == "我在医院工作"
