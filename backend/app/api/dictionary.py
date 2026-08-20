from fastapi import APIRouter, Depends, Query

from app.db.redis import RedisCache, get_cache
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.dictionary import DictionaryEntry
from app.services.dictionary_service import build_dictionary_provider

router = APIRouter(prefix="/dictionary", tags=["dictionary"])


@router.get("/{word}", response_model=DictionaryEntry)
async def lookup_word(
    word: str,
    context: str | None = Query(default=None),
    cache: RedisCache = Depends(get_cache),
    db: AsyncSession = Depends(get_db),
) -> DictionaryEntry:
    provider = build_dictionary_provider(cache, enrich=True, db=db)
    return await provider.lookup(word, context)
