from fastapi import APIRouter, Depends, Query

from app.db.redis import RedisCache, get_cache
from app.schemas.dictionary import DictionaryEntry
from app.services.dictionary_service import build_dictionary_provider

router = APIRouter(prefix="/dictionary", tags=["dictionary"])


@router.get("/{word}", response_model=DictionaryEntry)
async def lookup_word(
    word: str,
    context: str | None = Query(default=None),
    cache: RedisCache = Depends(get_cache),
) -> DictionaryEntry:
    provider = build_dictionary_provider(cache, enrich=True)
    return await provider.lookup(word, context)
