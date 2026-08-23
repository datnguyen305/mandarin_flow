from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import RedisCache
from app.services.asr_service import build_asr_provider
from app.services.dictionary_service import build_dictionary_provider
from app.services.pronunciation_service import PypinyinPronunciationProvider
from app.services.segmentation_service import JiebaSegmentationProvider
from app.services.subtitle_nlp_service import build_subtitle_nlp_provider
from app.services.subtitle_service import SubtitleRetrievalProvider, SubtitleService
from app.services.translation_service import build_translation_provider
from app.services.youtube_service import YouTubeService
from app.services.video_topic_classifier import build_video_topic_classifier


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
        pronunciation_provider=PypinyinPronunciationProvider(),
        subtitle_nlp_provider=build_subtitle_nlp_provider(cache),
        translation_provider=translation_provider,
        dictionary_provider=dictionary_provider,
        video_topic_classifier=build_video_topic_classifier(),
    )
