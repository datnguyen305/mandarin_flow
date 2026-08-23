import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, bot_token: str | None = None) -> None:
        self.bot_token = bot_token or settings.telegram_bot_token

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and settings.telegram_admin_chat_id)

    async def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.bot_token:
            logger.warning("Telegram is not configured; skipping notification")
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(f"https://api.telegram.org/bot{self.bot_token}/{method}", json=payload)
                response.raise_for_status()
                data = response.json()
                if not data.get("ok"):
                    raise RuntimeError("Telegram API returned an unsuccessful response")
                return data.get("result")
        except httpx.HTTPStatusError as exc:
            if method == "editMessageText" and exc.response.status_code == 400:
                logger.warning("Telegram notification update was rejected", extra={"method": method, "status_code": 400})
            else:
                logger.exception("Telegram API call failed", extra={"method": method, "status_code": exc.response.status_code})
            return None
        except (httpx.HTTPError, ValueError, RuntimeError):
            logger.exception("Telegram API call failed", extra={"method": method})
            return None

    async def send_request(self, request_id: str, request_type: str, payload: dict[str, Any], reason: str) -> bool:
        if not self.enabled:
            return False
        if request_type == "cookie_update":
            text = (
                "MandarinFlow Agent\n\n"
                "Can cap nhat cookies YouTube\n"
                f"Video: {payload.get('youtube_url') or 'Video can xu ly'}\n\n"
                f"Ly do: {reason}\n\n"
                "Hay export cookies.txt tu cung trinh duyet dang xem duoc video, "
                "sau do upload trong trang /dev. Bot khong truy cap noi dung cookies."
            )
            result = await self._call(
                "sendMessage",
                {
                    "chat_id": settings.telegram_admin_chat_id,
                    "text": text,
                    "reply_markup": {"inline_keyboard": [[
                        {"text": "Approve export", "callback_data": f"approve:{request_id}"},
                        {"text": "Reject", "callback_data": f"reject:{request_id}"},
                    ]]},
                },
            )
            return result is not None
        if request_type == "video_import":
            text = (
                "MandarinFlow Agent\n\n"
                "De xuat import video\n"
                f"URL: {payload.get('youtube_url')}\n"
                f"Tags: {', '.join(payload.get('suggested_tags', [])) or 'Chua co'}\n\n"
                f"Ly do: {reason}\n\nRequest: {request_id}"
            )
            keyboard = [[
                {"text": "Approve", "callback_data": f"approve:{request_id}"},
                {"text": "Reject", "callback_data": f"reject:{request_id}"},
            ]]
        else:
            words = payload.get("words", [])
            preview = "\n".join(
                f"{item.get('simplified')} {item.get('pinyin') or ''} - {item.get('vi') or ''}" for item in words[:8]
            )
            if len(words) > 8:
                preview += f"\n... va {len(words) - 8} tu khac"
            text = (
                "MandarinFlow Agent\n\n"
                f"De xuat them {len(words)} tu\n\n{preview}\n\n"
                f"Ly do: {reason}\n\nRequest: {request_id}"
            )
            keyboard = [[
                {"text": "Approve all", "callback_data": f"approve:{request_id}"},
                {"text": "Reject", "callback_data": f"reject:{request_id}"},
            ]]
        result = await self._call(
            "sendMessage",
            {"chat_id": settings.telegram_admin_chat_id, "text": text, "reply_markup": {"inline_keyboard": keyboard}},
        )
        return result is not None

    async def send_message(self, chat_id: str, text: str) -> bool:
        return (await self._call("sendMessage", {"chat_id": chat_id, "text": text})) is not None

    async def answer_callback(self, callback_id: str, text: str) -> None:
        await self._call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text, "show_alert": False})

    async def update_callback_message(self, callback_query: dict[str, Any], text: str) -> None:
        message = callback_query.get("message") or {}
        chat = message.get("chat") or {}
        if message.get("message_id") and chat.get("id"):
            await self._call("editMessageText", {"chat_id": chat["id"], "message_id": message["message_id"], "text": text})
