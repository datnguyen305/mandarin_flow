import uuid

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
    guest_id = uuid.UUID("11111111-1111-1111-1111-111111111111")


class FakeVocabularyRepository:
    async def find_for_guest_by_word(self, guest_id: uuid.UUID, word: str) -> FakeSavedItem | None:
        return None

    async def find_video_and_subtitle(self, youtube_video_id: str, subtitle_id: int) -> tuple[FakeVideo, FakeSubtitle]:
        return FakeVideo(), FakeSubtitle()

    async def save(self, *args) -> FakeSavedItem:
        return FakeSavedItem()

    async def list_for_guest(self, guest_id: uuid.UUID) -> list[FakeSavedItem]:
        return [FakeSavedItem()] if guest_id == FakeSavedItem.guest_id else []

    async def delete_for_guest(self, vocabulary_id: int, guest_id: uuid.UUID) -> bool:
        return vocabulary_id == FakeSavedItem.id and guest_id == FakeSavedItem.guest_id


@pytest.mark.asyncio
async def test_save_and_retrieve_vocabulary() -> None:
    service = VocabularyService(FakeDb())  # type: ignore[arg-type]
    service.repo = FakeVocabularyRepository()  # type: ignore[assignment]

    guest_id = FakeSavedItem.guest_id
    saved_id, save_status = await service.save(guest_id, "医院", "yīyuàn", "bệnh viện", "abc123abc12", 20, 12.5)
    items = await service.list_for_guest(guest_id)

    assert saved_id > 0
    assert save_status == "saved"
    assert len(items) == 1
    assert items[0].word == "医院"
    assert items[0].subtitle_sentence == "我在医院工作"


@pytest.mark.asyncio
async def test_duplicate_word_is_not_saved_twice() -> None:
    service = VocabularyService(FakeDb())  # type: ignore[arg-type]
    repository = FakeVocabularyRepository()
    repository.find_for_guest_by_word = lambda guest_id, word: _async_existing_word(guest_id, word)  # type: ignore[method-assign]
    service.repo = repository  # type: ignore[assignment]

    saved_id, save_status = await service.save(FakeSavedItem.guest_id, " 医院 ", None, None, "abc123abc12", 20, 12.5)

    assert saved_id == FakeSavedItem.id
    assert save_status == "already_saved"


async def _async_existing_word(guest_id: uuid.UUID, word: str) -> FakeSavedItem | None:
    return FakeSavedItem() if guest_id == FakeSavedItem.guest_id and word == "医院" else None


@pytest.mark.asyncio
async def test_guest_cannot_delete_another_guests_vocabulary() -> None:
    service = VocabularyService(FakeDb())  # type: ignore[arg-type]
    service.repo = FakeVocabularyRepository()  # type: ignore[assignment]

    another_guest = uuid.UUID("22222222-2222-2222-2222-222222222222")

    assert await service.list_for_guest(another_guest) == []
    assert await service.delete_for_guest(FakeSavedItem.id, another_guest) is False
    assert await service.delete_for_guest(FakeSavedItem.id, FakeSavedItem.guest_id) is True
