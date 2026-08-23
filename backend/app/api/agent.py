from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_or_create_guest, require_dev_access
from app.core.config import settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models import AgentRequest
from app.schemas.agent import AgentRequestResponse, AgentRequestView, ChatAgentRequest, ChatAgentResponse, CookieAgentRequest, CookieExportResult, VocabularyAgentRequest, VideoAgentRequest
from app.services.agent_request_service import AgentRequestService
from app.services.assistant_service import AssistantService
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatAgentResponse)
async def chat_with_assistant(
    payload: ChatAgentRequest,
    db: AsyncSession = Depends(get_db),
    guest=Depends(get_or_create_guest),
) -> ChatAgentResponse:
    reply, youtube_url, pending_action = await AssistantService().reply(payload)
    if pending_action and youtube_url:
        telegram = TelegramService()
        if not telegram.enabled:
            return ChatAgentResponse(reply="Telegram approval chưa được cấu hình nên tôi chưa tạo yêu cầu import.", youtube_url=youtube_url)
        request_payload = VideoAgentRequest(youtube_url=youtube_url, reason="Import requested by MandarinFlow chatbot")
        request_id, request_status, request_count = await AgentRequestService(db, telegram).request_video(
            request_payload,
            "chatbot",
            str(guest.id),
        )
        if request_status == "already_exists":
            return ChatAgentResponse(reply="Video này đã có trong MandarinFlow.", youtube_url=youtube_url)
        if request_status == "limit_reached":
            return ChatAgentResponse(
                reply=f"Bạn đã dùng hết {settings.chatbot_video_request_limit} lượt request import cho phiên này.",
                youtube_url=youtube_url,
                import_status="limit_reached",
            )
        pending_action.update({"request_id": request_id, "approval_channel": "telegram"})
        reply = f"Đã gửi yêu cầu import vào Telegram để bạn duyệt. Request: {request_id}"
    return ChatAgentResponse(reply=reply, youtube_url=youtube_url, pending_action=pending_action)


@router.post("/requests/video", response_model=AgentRequestResponse)
async def request_video_import(payload: VideoAgentRequest, db: AsyncSession = Depends(get_db), _: None = Depends(require_dev_access)) -> AgentRequestResponse:
    request_id, request_status, skipped = await AgentRequestService(db).request_video(payload)
    return AgentRequestResponse(request_id=request_id, status=request_status, skipped_count=skipped)


@router.post("/requests/vocabulary", response_model=AgentRequestResponse)
async def request_vocabulary_import(payload: VocabularyAgentRequest, db: AsyncSession = Depends(get_db), _: None = Depends(require_dev_access)) -> AgentRequestResponse:
    request_id, request_status, skipped = await AgentRequestService(db).request_vocabulary(payload)
    return AgentRequestResponse(request_id=request_id, status=request_status, skipped_count=skipped)


@router.post("/requests/cookies", response_model=AgentRequestResponse)
async def request_cookie_update(payload: CookieAgentRequest, db: AsyncSession = Depends(get_db), _: None = Depends(require_dev_access)) -> AgentRequestResponse:
    request_id, request_status, skipped = await AgentRequestService(db).request_cookie_update(payload)
    return AgentRequestResponse(request_id=request_id, status=request_status, skipped_count=skipped)


@router.get("/requests", response_model=list[AgentRequestView])
async def list_agent_requests(db: AsyncSession = Depends(get_db), _: None = Depends(require_dev_access)) -> list[AgentRequestView]:
    result = await db.execute(select(AgentRequest).order_by(AgentRequest.created_at.desc()).limit(100))
    return [AgentRequestView.model_validate(item) for item in result.scalars()]


@router.get("/requests/{request_id}", response_model=AgentRequestView)
async def get_agent_request(request_id: str, db: AsyncSession = Depends(get_db), _: None = Depends(require_dev_access)) -> AgentRequestView:
    request = await AgentRequestService(db).get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Agent request not found")
    return AgentRequestView.model_validate(request)


@router.post("/requests/{request_id}/approve", response_model=AgentRequestView)
async def approve_agent_request(request_id: str, db: AsyncSession = Depends(get_db), _: None = Depends(require_dev_access)) -> AgentRequestView:
    try:
        request = await AgentRequestService(db).approve(request_id, "api-admin")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentRequestView.model_validate(request)


@router.post("/requests/{request_id}/reject", response_model=AgentRequestView)
async def reject_agent_request(request_id: str, db: AsyncSession = Depends(get_db), _: None = Depends(require_dev_access)) -> AgentRequestView:
    try:
        request = await AgentRequestService(db).reject(request_id, "api-admin")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentRequestView.model_validate(request)


@router.post("/requests/{request_id}/cookie-export-result", response_model=AgentRequestView)
async def complete_cookie_export(
    request_id: str,
    payload: CookieExportResult,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_dev_access),
) -> AgentRequestView:
    try:
        request = await AgentRequestService(db).complete_cookie_export(request_id, payload.success, payload.error)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentRequestView.model_validate(request)


@router.post("/integrations/telegram/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not settings.telegram_webhook_secret or x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    update: dict[str, Any] = await request.json()
    callback = update.get("callback_query")
    telegram = TelegramService()
    if callback:
        user_id = str((callback.get("from") or {}).get("id", ""))
        if not settings.telegram_allowed_user_id or user_id != settings.telegram_allowed_user_id:
            await telegram.answer_callback(callback.get("id", ""), "Unauthorized")
            return
        await _handle_telegram_callback(callback, db, telegram, user_id)
        return

    message = update.get("message") or {}
    user_id = str((message.get("from") or {}).get("id", ""))
    chat_id = str((message.get("chat") or {}).get("id", ""))
    if not settings.telegram_allowed_user_id or user_id != settings.telegram_allowed_user_id:
        return
    if settings.telegram_admin_chat_id and chat_id != settings.telegram_admin_chat_id:
        return
    await _handle_telegram_message(str(message.get("text") or ""), chat_id, db, telegram, user_id)


async def _handle_telegram_callback(callback: dict[str, Any], db: AsyncSession, telegram: TelegramService, user_id: str) -> None:
    action, separator, request_id = str(callback.get("data", "")).partition(":")
    if not separator or action not in {"approve", "reject"} or not request_id:
        await telegram.answer_callback(callback.get("id", ""), "Invalid request")
        return
    service = AgentRequestService(db, telegram)
    try:
        result = await (service.approve(request_id, f"telegram:{user_id}") if action == "approve" else service.reject(request_id, f"telegram:{user_id}"))
        message = f"Request {result.id}: {result.status}"
    except ValueError as exc:
        message = str(exc)
    await telegram.answer_callback(callback.get("id", ""), message[:190])
    await telegram.update_callback_message(callback, message)


async def _handle_telegram_message(text: str, chat_id: str, db: AsyncSession, telegram: TelegramService, user_id: str) -> None:
    command, _, argument = text.strip().partition(" ")
    normalized_command = command.split("@", 1)[0].casefold()
    if normalized_command in {"/start", "/help"}:
        await telegram.send_message(chat_id, "MandarinFlow Bot\n\nGửi /import <YouTube URL> hoặc gửi trực tiếp một URL YouTube để tạo yêu cầu import. Bot sẽ gửi nút Approve trước khi xử lý.")
        return
    url = argument.strip() if normalized_command == "/import" else text.strip()
    if normalized_command != "/import" and not url.lower().startswith(("https://youtube.com", "https://www.youtube.com", "https://youtu.be", "https://m.youtube.com")):
        await telegram.send_message(chat_id, "Lệnh không hợp lệ. Dùng: /import <YouTube URL>")
        return
    if not url:
        await telegram.send_message(chat_id, "Thiếu URL. Dùng: /import <YouTube URL>")
        return
    try:
        payload = VideoAgentRequest(youtube_url=url, reason="Import video requested via Telegram")
        request_id, request_status, _ = await AgentRequestService(db, telegram).request_video(payload, f"telegram:{user_id}")
    except (ValidationError, AppError, ValueError):
        await telegram.send_message(chat_id, "URL YouTube không hợp lệ hoặc không thể xử lý.")
        return
    if request_status == "already_exists":
        await telegram.send_message(chat_id, "Video này đã có trong MandarinFlow.")
        return
    await telegram.send_message(chat_id, f"Đã tạo yêu cầu import {request_id}. Hãy bấm Approve trong tin nhắn xác nhận để bắt đầu xử lý.")
