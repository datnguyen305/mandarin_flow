from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_or_create_guest
from app.db.session import get_db
from app.models import GuestSession
from app.schemas.vocabulary import SaveVocabularyRequest, SaveVocabularyResponse, SavedVocabularyResponse
from app.services.vocabulary_service import VocabularyService

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.post("", response_model=SaveVocabularyResponse)
async def save_vocabulary(
    payload: SaveVocabularyRequest,
    db: AsyncSession = Depends(get_db),
    guest: GuestSession = Depends(get_or_create_guest),
) -> SaveVocabularyResponse:
    service = VocabularyService(db)
    vocabulary_id, save_status = await service.save(
        guest_id=guest.id,
        word=payload.word,
        pinyin=payload.pinyin,
        meaning=payload.meaning,
        youtube_video_id=payload.youtube_video_id,
        subtitle_id=payload.subtitle_id,
        timestamp=payload.timestamp,
    )
    return SaveVocabularyResponse(id=vocabulary_id, status=save_status)


@router.get("", response_model=list[SavedVocabularyResponse])
async def list_vocabulary(
    db: AsyncSession = Depends(get_db),
    guest: GuestSession = Depends(get_or_create_guest),
) -> list[SavedVocabularyResponse]:
    return await VocabularyService(db).list_for_guest(guest.id)


@router.delete("/{vocabulary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vocabulary(
    vocabulary_id: int,
    db: AsyncSession = Depends(get_db),
    guest: GuestSession = Depends(get_or_create_guest),
) -> None:
    # Deletion is intentionally idempotent so stale guest lists do not surface a false error.
    await VocabularyService(db).delete_for_guest(vocabulary_id, guest.id)
