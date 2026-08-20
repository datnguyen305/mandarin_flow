import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import suppress
from dataclasses import dataclass, field

from app.api.deps import build_subtitle_service
from app.db.redis import RedisCache
from app.db.session import AsyncSessionLocal
from app.repositories.batch_repository import BatchRepository
from app.repositories.video_repository import VideoRepository
from app.schemas.subtitle import SubtitleBatchResponse, SubtitleProcessingProgress

logger = logging.getLogger(__name__)


@dataclass
class VideoQueueState:
    task: asyncio.Task | None = None
    priority_batches: list[int] = field(default_factory=list)


class SubtitleEventBroker:
    def __init__(self) -> None:
        self.subscribers: dict[str, set[asyncio.Queue[dict]]] = defaultdict(set)

    async def publish(self, video_id: str, event: str, data: dict) -> None:
        payload = {"event": event, "data": data}
        for queue in list(self.subscribers.get(video_id, set())):
            await queue.put(payload)

    async def subscribe(self, video_id: str) -> AsyncGenerator[dict, None]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        self.subscribers[video_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self.subscribers[video_id].discard(queue)


class SubtitleProcessingQueue(ABC):
    @abstractmethod
    async def enqueue_video(self, video_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def prioritize_batch(self, video_id: str, playback_time: float) -> None:
        raise NotImplementedError


class InMemorySubtitleProcessingQueue(SubtitleProcessingQueue):
    def __init__(self, broker: SubtitleEventBroker) -> None:
        self.broker = broker
        self.states: dict[str, VideoQueueState] = defaultdict(VideoQueueState)
        self.lock = asyncio.Lock()

    async def enqueue_video(self, video_id: str) -> None:
        async with self.lock:
            state = self.states[video_id]
            if state.task is None or state.task.done():
                state.task = asyncio.create_task(self._worker(video_id))

    async def prioritize_batch(self, video_id: str, playback_time: float) -> None:
        async with AsyncSessionLocal() as db:
            video = await VideoRepository(db).get_by_youtube_id(video_id)
            if video is None:
                return
            batches = await BatchRepository(db).list_for_video(video.id)
        containing = [batch.batch_index for batch in batches if batch.start_time <= playback_time < batch.end_time]
        if not containing:
            return
        target = containing[0]
        priority = [target, target + 1, target + 2]
        async with self.lock:
            state = self.states[video_id]
            for batch_index in priority:
                if batch_index not in state.priority_batches:
                    state.priority_batches.append(batch_index)
        await self.enqueue_video(video_id)

    async def retry_batch(self, video_id: str, batch_index: int) -> None:
        async with AsyncSessionLocal() as db:
            video = await VideoRepository(db).get_by_youtube_id(video_id)
            if video is None:
                return
            await BatchRepository(db).mark_status(video.id, batch_index, "pending")
            await db.commit()
        async with self.lock:
            state = self.states[video_id]
            if batch_index not in state.priority_batches:
                state.priority_batches.insert(0, batch_index)
        await self.enqueue_video(video_id)

    async def _worker(self, video_id: str) -> None:
        await self.broker.publish(video_id, "processing_started", {"video_id": video_id})
        while True:
            next_batch = await self._next_batch(video_id)
            if next_batch is None:
                progress = await self._progress(video_id)
                if progress and progress.status == "completed":
                    await self.broker.publish(video_id, "processing_completed", {"video_id": video_id})
                return

            async with AsyncSessionLocal() as db:
                service = build_subtitle_service(db, RedisCache(None))
                try:
                    batch = await service.process_batch(video_id, next_batch)
                    await self.broker.publish(video_id, "subtitle_batch", batch.model_dump())
                    progress = await service.progress_for_youtube_id(video_id)
                    await self.broker.publish(video_id, "processing_progress", progress.model_dump())
                except Exception as exc:
                    await self.broker.publish(
                        video_id,
                        "processing_failed",
                        {"video_id": video_id, "batch_index": next_batch, "message": str(exc)},
                    )
                    logger.exception("subtitle worker batch failed", extra={"video_id": video_id, "batch_index": next_batch})

    async def _next_batch(self, video_id: str) -> int | None:
        async with AsyncSessionLocal() as db:
            video = await VideoRepository(db).get_by_youtube_id(video_id)
            if video is None:
                return None
            batches = await BatchRepository(db).list_for_video(video.id)
        pending = {batch.batch_index for batch in batches if batch.status == "pending"}
        if not pending:
            return None

        async with self.lock:
            state = self.states[video_id]
            order = prioritized_batch_order(pending, state.priority_batches)
            state.priority_batches = [batch_index for batch_index in state.priority_batches if batch_index not in pending]
        return order[0] if order else None

    async def _progress(self, video_id: str) -> SubtitleProcessingProgress | None:
        async with AsyncSessionLocal() as db:
            service = build_subtitle_service(db, RedisCache(None))
            with suppress(Exception):
                return await service.progress_for_youtube_id(video_id)
        return None


def format_sse(event: str, data: dict, event_id: str | None = None) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False, default=str)}")
    return "\n".join(lines) + "\n\n"


subtitle_event_broker = SubtitleEventBroker()
subtitle_processing_queue = InMemorySubtitleProcessingQueue(subtitle_event_broker)


def prioritized_batch_order(pending_batches: set[int], priority_batches: list[int]) -> list[int]:
    priority = []
    for batch_index in priority_batches:
        if batch_index in pending_batches and batch_index not in priority:
            priority.append(batch_index)
    remaining = sorted(batch_index for batch_index in pending_batches if batch_index not in priority)
    return [*priority, *remaining]
