import asyncio
import hashlib
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import AgentRequest, NormalizedDictionaryEntry
from app.repositories.video_repository import VideoRepository
from app.schemas.agent import CookieAgentRequest, VocabularyAgentRequest, VideoAgentRequest
from app.services.telegram_service import TelegramService
from app.services.youtube_service import YouTubeService

logger = logging.getLogger(__name__)
ACTIVE_REQUEST_STATUSES = {"pending", "approved", "executing"}


class AgentRequestService:
    def __init__(self, db: AsyncSession, telegram: TelegramService | None = None) -> None:
        self.db = db
        self.telegram = telegram or TelegramService()

    async def request_video(
        self,
        payload: VideoAgentRequest,
        requested_by: str = "agent",
        guest_id: str | None = None,
    ) -> tuple[str | None, str, int]:
        video_id = YouTubeService().extract_video_id(str(payload.youtube_url))
        existing_video = await VideoRepository(self.db).get_by_youtube_id(video_id)
        # A failed video may be retried after the user refreshes YouTube cookies.
        if existing_video is not None and existing_video.processing_status != "failed":
            return None, "already_exists", 0
        existing = await self._active_request("video_import", video_id)
        if existing:
            # An active approval request is not the same as an imported video.
            # Return its real state so callers can approve or inspect it instead
            # of repeatedly creating duplicate requests.
            if existing.status == "pending" and existing.error:
                await self._notify(existing)
            return existing.id, "pending_approval", 0
        if guest_id is not None:
            request_count = await self._guest_video_request_count(guest_id)
            if request_count >= settings.chatbot_video_request_limit:
                return None, "limit_reached", request_count
        request_id = self._new_id()
        request = AgentRequest(
            id=request_id,
            type="video_import",
            status="pending",
            payload={"youtube_url": str(payload.youtube_url), "youtube_video_id": video_id, "suggested_tags": payload.suggested_tags},
            reason=payload.reason,
            requested_by=requested_by,
            guest_id=guest_id,
            expires_at=self._expires_at(),
        )
        self.db.add(request)
        await self.db.commit()
        await self._notify(request)
        return request_id, "pending_approval", 0

    async def _guest_video_request_count(self, guest_id: str) -> int:
        result = await self.db.execute(
            select(func.count(AgentRequest.id)).where(
                AgentRequest.guest_id == guest_id,
                AgentRequest.type == "video_import",
            )
        )
        return int(result.scalar_one())

    async def request_vocabulary(self, payload: VocabularyAgentRequest) -> tuple[str | None, str, int]:
        items = await self._filter_existing_words(payload)
        active_words = await self._active_vocabulary_words()
        items = [item for item in items if item.simplified not in active_words and (item.traditional or item.simplified) not in active_words]
        skipped = len(payload.words) - len(items)
        if not items:
            return None, "already_exists", skipped
        request_id = self._new_id()
        request = AgentRequest(
            id=request_id,
            type="vocabulary_import",
            status="pending",
            payload={"words": [item.model_dump() for item in items]},
            reason=payload.reason,
            requested_by="agent",
            expires_at=self._expires_at(),
        )
        self.db.add(request)
        await self.db.commit()
        await self._notify(request)
        return request_id, "pending_approval", skipped

    async def request_cookie_update(self, payload: CookieAgentRequest) -> tuple[str, str, int]:
        request_id = self._new_id()
        request = AgentRequest(
            id=request_id,
            type="cookie_update",
            status="pending",
            payload={"youtube_url": str(payload.youtube_url) if payload.youtube_url else None},
            reason=payload.reason,
            requested_by="agent",
            expires_at=self._expires_at(),
        )
        self.db.add(request)
        await self.db.commit()
        await self._notify(request)
        return request_id, "manual_action_required", 0

    async def _filter_existing_words(self, payload: VocabularyAgentRequest):
        values = {item.simplified for item in payload.words} | {item.traditional for item in payload.words if item.traditional}
        result = await self.db.execute(
            select(NormalizedDictionaryEntry.simplified, NormalizedDictionaryEntry.traditional).where(
                or_(NormalizedDictionaryEntry.simplified.in_(values), NormalizedDictionaryEntry.traditional.in_(values))
            )
        )
        existing = {value for row in result.all() for value in row if value}
        return [item for item in payload.words if item.simplified not in existing and (item.traditional or item.simplified) not in existing]

    async def _active_request(self, request_type: str, video_id: str) -> AgentRequest | None:
        result = await self.db.execute(
            select(AgentRequest).where(AgentRequest.type == request_type, AgentRequest.status.in_(ACTIVE_REQUEST_STATUSES))
        )
        for request in result.scalars():
            if request.payload.get("youtube_video_id") == video_id:
                return request
        return None

    async def _active_vocabulary_words(self) -> set[str]:
        result = await self.db.execute(
            select(AgentRequest).where(AgentRequest.type == "vocabulary_import", AgentRequest.status.in_(ACTIVE_REQUEST_STATUSES))
        )
        words: set[str] = set()
        for request in result.scalars():
            words.update(
                value
                for item in request.payload.get("words", [])
                for value in (item.get("simplified"), item.get("traditional"))
                if value
            )
        return words

    async def _notify(self, request: AgentRequest) -> None:
        sent = await self.telegram.send_request(request.id, request.type, request.payload, request.reason)
        if sent:
            request.error = None
        else:
            request.error = "Telegram notification was not delivered; request remains pending."
        await self.db.commit()

    async def approve(self, request_id: str, approved_by: str) -> AgentRequest:
        request = await self._lock_request(request_id)
        if request.expires_at <= datetime.now(UTC):
            request.status = "expired"
            await self.db.commit()
            raise ValueError("Agent request has expired")
        self._ensure_pending(request)
        request.status = "approved"
        request.approved_by = approved_by
        request.approved_at = datetime.now(UTC)
        await self.db.commit()
        if request.type != "cookie_update":
            asyncio.create_task(self.execute(request_id))
        return request

    async def reject(self, request_id: str, rejected_by: str) -> AgentRequest:
        request = await self._lock_request(request_id)
        if request.expires_at <= datetime.now(UTC):
            request.status = "expired"
            await self.db.commit()
            raise ValueError("Agent request has expired")
        self._ensure_pending(request)
        request.status = "rejected"
        request.approved_by = rejected_by
        request.rejected_at = datetime.now(UTC)
        await self.db.commit()
        return request

    async def complete_cookie_export(self, request_id: str, success: bool, error: str | None = None) -> AgentRequest:
        request = await self._lock_request(request_id)
        if request.type != "cookie_update" or request.status != "approved":
            raise ValueError("Cookie request is not awaiting local export")
        request.status = "completed" if success else "failed"
        request.error = None if success else (error or "Cookie export failed")[:2000]
        request.executed_at = datetime.now(UTC)
        await self.db.commit()
        await self._notify_result(request, success)
        return request

    async def execute(self, request_id: str) -> None:
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            request = await db.get(AgentRequest, request_id)
            if request is None or request.status not in {"approved", "executing"}:
                return
            if request.type == "cookie_update":
                return
            if request.status == "approved":
                request.status = "executing"
                await db.commit()
            try:
                if request.type == "video_import":
                    await self._execute_video(db, request)
                elif request.type == "vocabulary_import":
                    await self._execute_vocabulary(db, request)
                else:
                    raise ValueError("Unsupported agent request type")
                request.status = "completed"
                request.executed_at = datetime.now(UTC)
                request.error = None
                await db.commit()
                await self._notify_result(request, True)
            except Exception as exc:
                request.status = "failed"
                request.error = str(exc)[:2000]
                await db.commit()
                logger.exception("Agent request execution failed", extra={"request_id": request_id})
                await self._notify_result(request, False)

    async def _execute_video(self, db: AsyncSession, request: AgentRequest) -> None:
        from app.api.deps import build_subtitle_service
        from app.db.redis import RedisCache
        from app.services.subtitle_queue import subtitle_processing_queue

        payload = request.payload
        service = build_subtitle_service(db, RedisCache(None))
        progress = await service.prepare_video(
            payload["youtube_url"], "zh", "vi", payload.get("suggested_tags", []), defer_content_preparation=True
        )
        if progress.status != "completed":
            await subtitle_processing_queue.enqueue_video(progress.video_id)
            for _ in range(60 * settings.agent_request_expiry_hours):
                await asyncio.sleep(2)
                current = await service.progress_for_youtube_id(progress.video_id)
                if current.status == "completed":
                    return
                if current.status == "failed":
                    failed_video = await VideoRepository(db).get_by_youtube_id(progress.video_id)
                    detail = getattr(failed_video, "processing_error", None) if failed_video is not None else None
                    code = getattr(failed_video, "processing_error_code", None) if failed_video is not None else None
                    raise RuntimeError(f"{code}: {detail}" if code and detail else detail or "Video processing failed")
            raise TimeoutError("Video processing timed out")

    async def _execute_vocabulary(self, db: AsyncSession, request: AgentRequest) -> None:
        existing_result = await db.execute(select(NormalizedDictionaryEntry))
        existing = {value for entry in existing_result.scalars() for value in (entry.simplified, entry.traditional)}
        for item in request.payload.get("words", []):
            if item["simplified"] in existing or item.get("traditional") in existing:
                continue
            simplified = item["simplified"]
            traditional = item.get("traditional") or simplified
            reading = {
                "pinyin": item.get("pinyin"),
                "pinyin_number": item.get("pinyin_number"),
                "senses": [{
                    "pos": item.get("pos"),
                    "vi": item.get("vi"),
                    "definition_vi": item.get("definition_vi"),
                    "examples": item.get("examples", []),
                }],
            }
            normalized = {**item, "id": f"agent:{request.id}:{simplified}", "simplified": simplified, "traditional": traditional, "readings": [reading]}
            source_raw = dict(item)
            source_hash = hashlib.sha256(json.dumps(source_raw, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            db.add(NormalizedDictionaryEntry(
                id=normalized["id"][:64], simplified=simplified, traditional=traditional, entry_type="word",
                readings_json=[reading], references_json=[], hsk_level=item.get("hsk"), source_name="agent",
                source_raw_json=source_raw, source_hash=source_hash, normalized_json=normalized,
                status="completed", validation_issues=[], model=None,
            ))
            existing.update({simplified, traditional})
        await db.commit()

    async def _notify_result(self, request: AgentRequest, success: bool) -> None:
        if not self.telegram.enabled:
            return
        text = (
            f"{'Thanh cong' if success else 'That bai'}\n\nRequest: {request.id}\n"
            f"Trang thai: {request.status}"
            + (f"\nLoi: {request.error}" if request.error else "")
        )
        await self.telegram._call("sendMessage", {"chat_id": settings.telegram_admin_chat_id, "text": text})

    async def _lock_request(self, request_id: str) -> AgentRequest:
        request = await self.db.scalar(select(AgentRequest).where(AgentRequest.id == request_id).with_for_update())
        if request is None:
            raise ValueError("Agent request not found")
        return request

    def _ensure_pending(self, request: AgentRequest) -> None:
        if request.expires_at <= datetime.now(UTC):
            request.status = "expired"
            raise ValueError("Agent request has expired")
        if request.status != "pending":
            raise ValueError(f"Agent request is already {request.status}")

    async def get(self, request_id: str) -> AgentRequest | None:
        return await self.db.get(AgentRequest, request_id)

    def _new_id(self) -> str:
        return f"req_{secrets.token_urlsafe(12)}"

    def _expires_at(self) -> datetime:
        return datetime.now(UTC) + timedelta(hours=settings.agent_request_expiry_hours)


async def resume_agent_executions() -> None:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentRequest.id).where(
                AgentRequest.type.in_({"video_import", "vocabulary_import"}),
                AgentRequest.status.in_({"approved", "executing"}),
            )
        )
        request_ids = list(result.scalars())
    for request_id in request_ids:
        asyncio.create_task(AgentRequestService(None).execute(request_id))  # type: ignore[arg-type]
