import pytest

from app.core.config import settings
from app.schemas.agent import ChatAgentRequest
from app.services.assistant_service import AssistantService


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"output_text": "Xin chào, tôi có thể giúp bạn import video."}


class _FakeClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        return _FakeResponse()


@pytest.mark.asyncio
async def test_assistant_fallback_extracts_youtube_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openai_chat_api_key", None)

    reply, url, result = await AssistantService().reply(
        ChatAgentRequest(message="import https://www.youtube.com/watch?v=TOC78RUj8pg&list=abc", history=[]),
    )

    assert url == "https://www.youtube.com/watch?v=TOC78RUj8pg&list=abc"
    assert "đã nhận link" in reply.lower()
    assert result == {
        "name": "import_video",
        "arguments": {"youtube_url": "https://www.youtube.com/watch?v=TOC78RUj8pg&list=abc"},
        "requires_approval": True,
    }


def test_assistant_ignores_invalid_url() -> None:
    assert AssistantService().extract_youtube_url("https://example.com/watch?v=TOC78RUj8pg") is None


@pytest.mark.asyncio
async def test_assistant_returns_normal_response_without_tool(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_chat_api_key", None)
    monkeypatch.setattr("app.services.assistant_service.httpx.AsyncClient", lambda **kwargs: _FakeClient())

    reply, url, pending_action = await AssistantService().reply(
        ChatAgentRequest(message="Xin chào", history=[]),
    )

    assert reply == "Xin chào, tôi có thể giúp bạn import video."
    assert url is None
    assert pending_action is None
