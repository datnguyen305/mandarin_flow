import pytest

from app.core.config import settings
from app.schemas.agent import ChatAgentRequest
from app.services.assistant_service import AssistantService


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
