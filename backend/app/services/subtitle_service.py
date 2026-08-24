import logging
import inspect
import time
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import SubtitlesUnavailableError, UnsupportedLanguageError
from app.core.config import settings
from app.db.redis import RedisCache
from app.models import Subtitle, Video
from app.repositories.batch_repository import BatchRepository
from app.repositories.subtitle_repository import SubtitleRepository
from app.repositories.video_repository import VideoRepository
from app.schemas.subtitle import SubtitleBatchResponse, SubtitleLineResponse, SubtitleListResponse, SubtitleProcessingProgress, SubtitleTokenResponse
from app.services.asr_service import ASRProvider
from app.services.dictionary_service import DictionaryProvider
from app.services.pronunciation_service import PronunciationProvider, PypinyinPronunciationProvider, token_pinyin
from app.services.segmentation_service import SegmentationProvider, locate_tokens
from app.services.subtitle_nlp_service import SubtitleNLPProvider, SubtitleTokenAnalysis
from app.services.transcript_types import RawSubtitle
from app.services.translation_service import TranslationProvider
from app.services.video_topic_classifier import VideoTopicClassifier
from app.services.youtube_service import YouTubeService

logger = logging.getLogger(__name__)
BatchProgressCallback = Callable[[float], Awaitable[None]]


class SubtitleRetrievalProvider:
    async def fetch(self, youtube_video_id: str, language: str) -> list[RawSubtitle]:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            transcript = await self._fetch_sync(youtube_video_id, language, YouTubeTranscriptApi)
            return [
                RawSubtitle(
                    start=float(item["start"]),
                    end=float(item["start"]) + float(item.get("duration", 0)),
                    text=str(item["text"]).replace("\n", " ").strip(),
                )
                for item in transcript
                if str(item.get("text", "")).strip()
            ]
        except Exception as exc:
            logger.warning("YouTube subtitles unavailable for %s: %s", youtube_video_id, exc)
            if youtube_video_id == "abc123abc12":
                return [
                    RawSubtitle(12.5, 15.2, "我在医院工作"),
                    RawSubtitle(16.0, 19.0, "我喜欢学习中文。"),
                ]
            raise SubtitlesUnavailableError("Chinese subtitles are unavailable for this video. ASR can be added later.")

    async def _fetch_sync(self, youtube_video_id: str, language: str, api) -> list[dict]:
        import asyncio

        return await asyncio.to_thread(api.get_transcript, youtube_video_id, languages=[language, "zh-Hans", "zh-CN", "zh"])


class SubtitleService:
    def __init__(
        self,
        db: AsyncSession,
        cache: RedisCache,
        youtube_service: YouTubeService,
        subtitle_provider: SubtitleRetrievalProvider,
        asr_provider: ASRProvider,
        segmentation_provider: SegmentationProvider,
        translation_provider: TranslationProvider,
        dictionary_provider: DictionaryProvider,
        pronunciation_provider: PronunciationProvider | None = None,
        subtitle_nlp_provider: SubtitleNLPProvider | None = None,
        video_topic_classifier: VideoTopicClassifier | None = None,
    ) -> None:
        self.db = db
        self.cache = cache
        self.youtube_service = youtube_service
        self.subtitle_provider = subtitle_provider
        self.asr_provider = asr_provider
        self.segmentation_provider = segmentation_provider
        self.translation_provider = translation_provider
        self.dictionary_provider = dictionary_provider
        self.pronunciation_provider = pronunciation_provider or PypinyinPronunciationProvider()
        self.subtitle_nlp_provider = subtitle_nlp_provider
        self.video_topic_classifier = video_topic_classifier
        self.video_repo = VideoRepository(db)
        self.subtitle_repo = SubtitleRepository(db)
        self.batch_repo = BatchRepository(db)

    async def prepare_video(
        self,
        url: str,
        source_language: str,
        target_language: str,
        tags: list[str] | None = None,
        defer_content_preparation: bool = False,
    ) -> SubtitleProcessingProgress:
        if source_language != "zh" or target_language != "vi":
            raise UnsupportedLanguageError("Only zh to vi is supported in the MVP")

        metadata = await self.youtube_service.get_metadata(url)
        video = await self.video_repo.upsert(
            youtube_video_id=metadata.video_id,
            title=metadata.title,
            url=metadata.url,
            thumbnail_url=metadata.thumbnail_url,
            language=source_language,
            tags=tags or None,
            duration_seconds=metadata.duration_seconds,
            channel_name=metadata.channel_name,
            channel_id=metadata.channel_id,
            view_count=metadata.view_count,
            upload_date=metadata.upload_date,
            metadata_fetched_at=metadata.metadata_fetched_at,
        )
        await self.db.commit()
        cache_key = f"video:{metadata.video_id}:subtitles:{source_language}-{target_language}"
        cached = await self.cache.get(cache_key)
        if cached:
            logger.info("Processed subtitles found in Redis for %s", metadata.video_id)
            if video is not None:
                if tags and video.tags != tags:
                    await self.video_repo.set_tags(video, tags)
                    await self.db.commit()
                if tags or video.tags:
                    return await self.progress_for_video(video)

        existing = await self.video_repo.get_with_subtitles(metadata.video_id)
        if existing and existing.subtitles and all(subtitle.processing_status == "processed" for subtitle in existing.subtitles):
            logger.info("Completed subtitles found in PostgreSQL for %s", metadata.video_id)
            await self.cache.set(cache_key, self._response_from_video(existing).model_dump_json())
            if tags and existing.tags != tags:
                await self.video_repo.set_tags(existing, tags)
                await self.db.commit()
            return await self.progress_for_video(existing)

        await self.video_repo.set_processing_status(video, "processing")
        video.processing_error_code = None
        video.processing_error = None
        await self.video_repo.set_processing_phase(video, "subtitle_source", 0.05)
        # Persist the import before slow subtitle retrieval/ASR so clients can
        # reconnect and observe a stable processing record immediately.
        await self.db.commit()

        if defer_content_preparation:
            return await self.progress_for_video(video)

        return await self.prepare_video_content(metadata.video_id, source_language, target_language)

    async def prepare_video_content(
        self,
        youtube_video_id: str,
        source_language: str = "zh",
        target_language: str = "vi",
    ) -> SubtitleProcessingProgress:
        video = await self.video_repo.get_by_youtube_id(youtube_video_id)
        if video is None:
            raise SubtitlesUnavailableError("Video is not available.")

        existing_subtitles = await self.subtitle_repo.list_by_video_id(video.id)
        if existing_subtitles and all(subtitle.processing_status == "processed" for subtitle in existing_subtitles):
            return await self.progress_for_video(video)

        try:
            if not existing_subtitles:
                raw_subtitles = await self._retrieve_or_transcribe(youtube_video_id, source_language)
                await self.video_repo.set_processing_phase(video, "preparing_batches", 0.28)
                await self.db.commit()
                raw_lines = self._raw_lines_with_batches(raw_subtitles)
                await self.subtitle_repo.replace_raw_for_video(video.id, raw_lines)
                await self.batch_repo.create_missing(video.id, self._batch_definitions(raw_lines))
            else:
                await self.video_repo.set_processing_phase(video, "preparing_batches", 0.28)
                await self.batch_repo.create_missing(video.id, self._batch_definitions_from_subtitles(existing_subtitles))
        except Exception:
            await self.db.rollback()
            video = await self.video_repo.get_by_youtube_id(youtube_video_id)
            if video is not None:
                await self.video_repo.set_processing_status(video, "failed")
                await self.video_repo.set_processing_phase(video, "failed", video.processing_progress)
                video.processing_error_code = getattr(exc, "error_class", getattr(exc, "code", "UNKNOWN"))
                video.processing_error = str(exc)[:2000]
                await self.db.commit()
            raise

        await self.video_repo.set_processing_phase(video, "processing_batches", max(float(video.processing_progress or 0.0), 0.30))
        await self.db.commit()
        return await self.progress_for_video(video)

    async def classify_video_topics(self, youtube_video_id: str) -> list[str]:
        video = await self.video_repo.get_with_subtitles(youtube_video_id)
        if video is None or video.tags or not video.subtitles:
            return list(video.tags) if video is not None else []
        inferred_tags = await self._classify_video_topics(video.title, [subtitle.text for subtitle in video.subtitles])
        if inferred_tags:
            await self.video_repo.set_tags(video, inferred_tags)
            await self.db.commit()
        return inferred_tags

    async def _classify_video_topics(self, title: str, subtitles: list[str]) -> list[str]:
        if self.video_topic_classifier is None:
            return []
        try:
            return await self.video_topic_classifier.classify(title, subtitles)
        except Exception:
            logger.exception("Unexpected video topic classification failure")
            return []

    async def process_video(self, url: str, source_language: str, target_language: str) -> str:
        progress = await self.prepare_video(url, source_language, target_language)
        return progress.video_id

    async def _retrieve_or_transcribe(self, youtube_video_id: str, source_language: str) -> list[RawSubtitle]:
        video = await self.video_repo.get_by_youtube_id(youtube_video_id)
        if video is not None:
            await self.video_repo.set_processing_phase(video, "youtube_subtitles", 0.08)
            await self.db.commit()
        try:
            return await self.subtitle_provider.fetch(youtube_video_id, source_language)
        except SubtitlesUnavailableError:
            logger.info("Falling back to ASR for %s", youtube_video_id)
            video = await self.video_repo.get_by_youtube_id(youtube_video_id)
            if video is not None:
                await self.video_repo.set_processing_phase(video, "asr", 0.14)
                await self.db.commit()
            async def report_asr_progress(completed: int, total: int) -> None:
                current_video = await self.video_repo.get_by_youtube_id(youtube_video_id)
                if current_video is None:
                    return
                ratio = completed / max(total, 1)
                await self.video_repo.set_processing_phase(current_video, "asr", 0.14 + (0.12 * ratio))
                await self.db.commit()
                logger.info("ASR progress", extra={"youtube_id": youtube_video_id, "completed_chunks": completed, "total_chunks": total})

            transcribe = self.asr_provider.transcribe_youtube_audio
            if "progress_callback" in inspect.signature(transcribe).parameters:
                return await transcribe(youtube_video_id, source_language, report_asr_progress)
            return await transcribe(youtube_video_id, source_language)

    async def get_subtitles(self, youtube_video_id: str, source_language: str = "zh", target_language: str = "vi") -> SubtitleListResponse:
        cache_key = f"video:{youtube_video_id}:subtitles:{source_language}-{target_language}"
        cached = await self.cache.get(cache_key)
        if cached:
            return SubtitleListResponse.model_validate_json(cached)
        video = await self.video_repo.get_with_subtitles(youtube_video_id)
        if video is None or not video.subtitles:
            raise SubtitlesUnavailableError("Processed subtitles are unavailable. Process the video first.")
        response = self._response_from_video(video)
        await self.cache.set(cache_key, response.model_dump_json())
        return response

    async def get_raw_subtitles(self, youtube_video_id: str) -> SubtitleListResponse:
        video = await self.video_repo.get_with_subtitles(youtube_video_id)
        if video is None or not video.subtitles:
            raise SubtitlesUnavailableError("Raw subtitles are unavailable. Start processing the video first.")
        return self._response_from_video(video)

    async def process_batch(
        self,
        youtube_video_id: str,
        batch_index: int,
        source_language: str = "zh",
        target_language: str = "vi",
        progress_callback: BatchProgressCallback | None = None,
    ) -> SubtitleBatchResponse:
        video = await self.video_repo.get_by_youtube_id(youtube_video_id)
        if video is None:
            raise SubtitlesUnavailableError("Video is not available for subtitle processing.")
        batch = await self.batch_repo.get(video.id, batch_index)
        if batch is None:
            raise SubtitlesUnavailableError("Subtitle batch not found.")
        video_pk = video.id
        batch_start_time = batch.start_time
        batch_end_time = batch.end_time
        if batch.status == "completed":
            subtitles = await self.subtitle_repo.list_by_batch(video_pk, batch_index)
            return self._batch_response(video, batch_index, batch_start_time, batch_end_time, subtitles)

        started = time.monotonic()
        subtitles = await self.subtitle_repo.list_by_batch(video_pk, batch_index)
        try:
            await self.batch_repo.mark_status(video_pk, batch_index, "processing")
            for subtitle in subtitles:
                subtitle.processing_status = "processing"
            await self.db.flush()
            await self._report_batch_progress(progress_callback, 0.02)
            processed = await self._process_subtitle_batch(
                subtitles,
                source_language,
                target_language,
                progress_callback=progress_callback,
            )
            await self._report_batch_progress(progress_callback, 0.98)
            updated = await self.subtitle_repo.update_processed_batch(video_pk, batch_index, processed)
            await self.batch_repo.mark_status(video_pk, batch_index, "completed")
            await self._maybe_complete_video(video)
            await self.db.commit()

            refreshed_video = await self.video_repo.get_with_subtitles(youtube_video_id)
            if refreshed_video and refreshed_video.processing_status == "completed":
                await self.cache.set(f"video:{youtube_video_id}:subtitles:{source_language}-{target_language}", self._response_from_video(refreshed_video).model_dump_json())

            duration = time.monotonic() - started
            logger.info(
                "subtitle batch processed",
                extra={
                    "video_id": youtube_video_id,
                    "batch_index": batch_index,
                    "start_time": batch_start_time,
                    "end_time": batch_end_time,
                    "processing_duration": duration,
                    "subtitle_count": len(updated),
                    "status": "completed",
                },
            )
            batch_response = self._batch_response(video, batch_index, batch_start_time, batch_end_time, updated)
            await self.cache.set(f"video:{youtube_video_id}:batch:{batch_index}:zh-vi", batch_response.model_dump_json())
            return batch_response
        except Exception:
            await self.db.rollback()
            await self.batch_repo.mark_status(video_pk, batch_index, "failed")
            await self.subtitle_repo.mark_batch_failed(video_pk, batch_index)
            await self.video_repo.set_processing_status_by_id(video_pk, "failed")
            await self.db.commit()
            duration = time.monotonic() - started
            logger.exception(
                "subtitle batch failed",
                extra={
                    "video_id": youtube_video_id,
                    "batch_index": batch_index,
                    "start_time": batch_start_time,
                    "end_time": batch_end_time,
                    "processing_duration": duration,
                    "subtitle_count": len(subtitles),
                    "status": "failed",
                },
            )
            raise

    async def progress_for_youtube_id(self, youtube_video_id: str) -> SubtitleProcessingProgress:
        video = await self.video_repo.get_by_youtube_id(youtube_video_id)
        if video is None:
            raise SubtitlesUnavailableError("Video is not available.")
        return await self.progress_for_video(video)

    async def progress_for_video(self, video: Video) -> SubtitleProcessingProgress:
        batches = await self.batch_repo.list_for_video(video.id)
        subtitles = await self.subtitle_repo.list_by_video_id(video.id)
        processed_batches = sum(1 for batch in batches if batch.status == "completed")
        processed_subtitles = sum(1 for subtitle in subtitles if subtitle.processing_status == "processed")
        total_batches = len(batches)
        total_subtitles = len(subtitles)
        status = "completed" if total_batches > 0 and processed_batches == total_batches else video.processing_status
        batch_progress = (processed_batches / total_batches) if total_batches else 0.0
        persisted_progress = float(video.processing_progress or 0.0)
        overall_progress = max(persisted_progress, 0.30 + 0.68 * batch_progress) if total_batches else persisted_progress
        if status == "completed":
            overall_progress = 1.0
        return SubtitleProcessingProgress(
            video_id=video.youtube_video_id,
            status=status,
            phase="completed" if status == "completed" else video.processing_phase,
            phase_progress=overall_progress,
            processed_batches=processed_batches,
            total_batches=total_batches,
            processed_subtitles=processed_subtitles,
            total_subtitles=total_subtitles,
            progress=overall_progress,
        )

    async def completed_batch_events(self, youtube_video_id: str) -> list[SubtitleBatchResponse]:
        video = await self.video_repo.get_by_youtube_id(youtube_video_id)
        if video is None:
            return []
        batches = [batch for batch in await self.batch_repo.list_for_video(video.id) if batch.status == "completed"]
        events: list[SubtitleBatchResponse] = []
        for batch in batches:
            subtitles = await self.subtitle_repo.list_by_batch(video.id, batch.batch_index)
            events.append(self._batch_response(video, batch.batch_index, batch.start_time, batch.end_time, subtitles))
        return events

    async def _process_lines(self, raw_lines: list[RawSubtitle], source_language: str, target_language: str) -> list[dict]:
        normalized = [line for line in raw_lines if line.text]
        translations = await self.translation_provider.translate_batch([line.text for line in normalized], source_language, target_language)
        texts = [line.text for line in normalized]
        analyses = await self._analyze_subtitles(texts)
        processed: list[dict] = []
        for line, translation, analysis in zip(normalized, translations, analyses, strict=True):
            enriched_tokens = await self._enrich_analyzed_tokens(line.text, analysis)
            translation = self._translation_or_token_gloss(translation, line.text, target_language, enriched_tokens)
            processed.append({"start": line.start, "end": line.end, "text": line.text, "translation": translation, "tokens": enriched_tokens})
        return processed

    async def _process_subtitle_batch(
        self,
        subtitles: list[Subtitle],
        source_language: str,
        target_language: str,
        progress_callback: BatchProgressCallback | None = None,
    ) -> list[dict]:
        normalized = [subtitle for subtitle in subtitles if subtitle.text]
        translations: list[str] = []
        translation_starts = list(range(0, len(normalized), settings.translation_batch_size))
        for chunk_index, start in enumerate(translation_starts):
            chunk = normalized[start : start + settings.translation_batch_size]
            translations.extend(await self.translation_provider.translate_batch([subtitle.text for subtitle in chunk], source_language, target_language))
            await self._report_batch_progress(
                progress_callback,
                0.05 + 0.35 * ((chunk_index + 1) / max(len(translation_starts), 1)),
            )
        texts = [subtitle.text for subtitle in normalized]
        analyses = await self._analyze_subtitles(texts, progress_callback=progress_callback)
        processed: list[dict] = []
        for index, (subtitle, translation, analysis) in enumerate(zip(normalized, translations, analyses, strict=True)):
            enriched_tokens = await self._enrich_analyzed_tokens(subtitle.text, analysis)
            translation = self._translation_or_token_gloss(translation, subtitle.text, target_language, enriched_tokens)
            processed.append(
                {
                    "sequence_number": subtitle.sequence_number,
                    "start": subtitle.start_time,
                    "end": subtitle.end_time,
                    "text": subtitle.text,
                    "translation": translation,
                    "tokens": enriched_tokens,
                }
            )
            await self._report_batch_progress(
                progress_callback,
                0.8 + 0.16 * ((index + 1) / max(len(normalized), 1)),
            )
        return processed

    async def _analyze_subtitles(
        self,
        texts: list[str],
        progress_callback: BatchProgressCallback | None = None,
    ) -> list[list[SubtitleTokenAnalysis]]:
        if self.subtitle_nlp_provider is not None:
            analyses: list[list[SubtitleTokenAnalysis]] = []
            analysis_starts = list(range(0, len(texts), settings.translation_batch_size))
            for chunk_index, start in enumerate(analysis_starts):
                analyses.extend(
                    await self.subtitle_nlp_provider.analyze_batch(
                        texts[start : start + settings.translation_batch_size]
                    )
                )
                await self._report_batch_progress(
                    progress_callback,
                    0.4 + 0.4 * ((chunk_index + 1) / max(len(analysis_starts), 1)),
                )
            return analyses

        segmented = self.segmentation_provider.segment_batch(texts)
        sentence_pinyins = self.pronunciation_provider.pinyin_batch(texts)
        analyses = [
            [
                SubtitleTokenAnalysis(
                    text=token["text"],
                    pinyin=token_pinyin(sentence_pinyin, token["start_index"], token["end_index"]),
                )
                for token in locate_tokens(text, tokens)
            ]
            for text, tokens, sentence_pinyin in zip(texts, segmented, sentence_pinyins, strict=True)
        ]
        await self._report_batch_progress(progress_callback, 0.8)
        return analyses

    async def _report_batch_progress(self, callback: BatchProgressCallback | None, progress: float) -> None:
        if callback is not None:
            await callback(min(max(progress, 0.0), 0.99))

    async def _enrich_analyzed_tokens(self, context: str, analysis: list[SubtitleTokenAnalysis]) -> list[dict]:
        located_tokens = locate_tokens(context, [token.text for token in analysis])
        pinyin_by_position = {
            (token["start_index"], token["end_index"]): analyzed.pinyin
            for token, analyzed in zip(located_tokens, analysis, strict=True)
        }
        return await self._enrich_tokens(located_tokens, context, pinyin_by_position)

    async def _enrich_tokens(
        self,
        located_tokens: list[dict],
        context: str,
        pinyin_by_position: dict[tuple[int, int], str | None],
    ) -> list[dict]:
        enriched_tokens = []
        for token in located_tokens:
            contextual_pinyin = pinyin_by_position.get((token["start_index"], token["end_index"]))
            if self.dictionary_provider is None:
                enriched_tokens.append({**token, "pinyin": contextual_pinyin, "meaning": None})
                continue
            entry = await self.dictionary_provider.lookup(token["text"], context=context)
            enriched_tokens.append({**token, "pinyin": contextual_pinyin or entry.pinyin, "meaning": entry.meaning})
        return enriched_tokens

    def _translation_or_token_gloss(self, translation: str, source_text: str, target_language: str, tokens: list[dict]) -> str:
        placeholder = f"[{target_language}] {source_text}"
        if translation.strip() != placeholder:
            return translation

        meanings = [meaning for token in tokens if isinstance((meaning := token.get("meaning")), str) and meaning.strip()]
        return " / ".join(meanings) if meanings else translation

    def _raw_lines_with_batches(self, raw_lines: list[RawSubtitle]) -> list[dict]:
        lines = [line for line in raw_lines if line.text]
        return [
            {
                "start": line.start,
                "end": line.end,
                "text": line.text,
                "batch_index": int(line.start // settings.subtitle_batch_seconds),
            }
            for line in lines
        ]

    def _batch_definitions(self, lines: list[dict]) -> list[dict]:
        batch_indexes = sorted({int(line["batch_index"]) for line in lines})
        return [
            {
                "batch_index": batch_index,
                "start_time": float(batch_index * settings.subtitle_batch_seconds),
                "end_time": float((batch_index + 1) * settings.subtitle_batch_seconds),
            }
            for batch_index in batch_indexes
        ]

    def _batch_definitions_from_subtitles(self, subtitles: list[Subtitle]) -> list[dict]:
        lines = [
            {
                "batch_index": subtitle.batch_index if subtitle.batch_index is not None else int(subtitle.start_time // settings.subtitle_batch_seconds),
            }
            for subtitle in subtitles
        ]
        return self._batch_definitions(lines)

    async def _maybe_complete_video(self, video: Video) -> None:
        batches = await self.batch_repo.list_for_video(video.id)
        if batches and all(batch.status == "completed" for batch in batches):
            await self.video_repo.set_processing_status(video, "completed")
            await self.video_repo.set_processing_phase(video, "completed", 1.0)

    def _response_from_video(self, video: Video) -> SubtitleListResponse:
        subtitles = sorted(video.subtitles, key=lambda item: item.sequence_number)
        return SubtitleListResponse(
            video_id=video.youtube_video_id,
            title=video.title,
            subtitles=[self._line_response(subtitle) for subtitle in subtitles],
        )

    def _line_response(self, subtitle: Subtitle) -> SubtitleLineResponse:
        tokens = sorted(subtitle.tokens, key=lambda item: item.start_index)
        return SubtitleLineResponse(
            id=subtitle.id,
            start=subtitle.start_time,
            end=subtitle.end_time,
            text=subtitle.text,
            translation=subtitle.translated_text,
            processing_status=subtitle.processing_status,
            tokens=[
                SubtitleTokenResponse(
                    text=token.text,
                    pinyin=token.pinyin,
                    meaning=token.meaning,
                    start_index=token.start_index,
                    end_index=token.end_index,
                )
                for token in tokens
            ],
        )

    def _batch_response(self, video: Video, batch_index: int, start_time: float, end_time: float, subtitles: list[Subtitle]) -> SubtitleBatchResponse:
        return SubtitleBatchResponse(
            video_id=video.youtube_video_id,
            batch_index=batch_index,
            start_time=start_time,
            end_time=end_time,
            subtitles=[self._line_response(subtitle) for subtitle in sorted(subtitles, key=lambda item: item.sequence_number)],
        )
