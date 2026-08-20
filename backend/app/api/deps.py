from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import RedisCache
from app.services.asr_service import build_asr_provider
from app.services.dictionary_service import build_dictionary_provider
from app.services.segmentation_service import JiebaSegmentationProvider
from app.services.subtitle_service import SubtitleRetrievalProvider, SubtitleService
from app.services.translation_service import build_translation_provider
from app.services.youtube_service import YouTubeService


def build_subtitle_service(db: AsyncSession, cache: RedisCache) -> SubtitleService:
    dictionary_provider = build_dictionary_provider(cache)
    translation_provider = build_translation_provider(cache)
    return SubtitleService(
        db=db,
        cache=cache,
        youtube_service=YouTubeService(),
        subtitle_provider=SubtitleRetrievalProvider(),
        asr_provider=build_asr_provider(),
        segmentation_provider=JiebaSegmentationProvider(),
        translation_provider=translation_provider,
        dictionary_provider=dictionary_provider,
    )
