from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core import config
from app.schemas.agent import VocabularyAgentRequest, VideoAgentRequest
from app.services.agent_request_service import AgentRequestService
from app.services.telegram_service import TelegramService


def test_video_agent_request_normalizes_tags() -> None:
    payload = VideoAgentRequest(
        youtube_url="https://www.youtube.com/watch?v=abc123abc12",
        reason="Phu hop voi nguoi hoc.",
        suggested_tags=[" Hoi thoai ", "hoi thoai", "Podcast"],
    )
    assert payload.suggested_tags == ["Hoi thoai", "Podcast"]


def test_vocabulary_agent_request_defaults_traditional_form() -> None:
    payload = VocabularyAgentRequest(words=[{"simplified": "银行", "vi": "ngân hàng"}], reason="Tu pho bien.")
    assert payload.words[0].traditional == "银行"


def test_agent_request_state_guard_rejects_non_pending() -> None:
    request = SimpleNamespace(status="completed", expires_at=datetime.now(UTC) + timedelta(hours=1))
    with pytest.raises(ValueError, match="already completed"):
        AgentRequestService._ensure_pending(AgentRequestService.__new__(AgentRequestService), request)


@pytest.mark.asyncio
async def test_telegram_approval_buttons_only_contain_request_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "telegram_admin_chat_id", "123")
    service = TelegramService("bot-token")
    captured: dict = {}

    async def fake_call(method: str, payload: dict):
        captured.update({"method": method, "payload": payload})
        return {"message_id": 1}

    monkeypatch.setattr(service, "_call", fake_call)
    sent = await service.send_request(
        "req_123",
        "video_import",
        {"youtube_url": "https://youtube.com/watch?v=abc123abc12", "suggested_tags": []},
        "reason",
    )

    assert sent is True
    assert captured["payload"]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "approve:req_123"
