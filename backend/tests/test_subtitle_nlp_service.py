import json

import pytest

from app.services.subtitle_nlp_service import (
    OpenAISubtitleNLPProvider,
    SubtitleNLPProvider,
    SubtitleTokenAnalysis,
)


class FakeResponse:
    def __init__(self, output: dict) -> None:
        self.output = output

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.output


class FakeClient:
    requests: list[dict] = []

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
        self.requests.append({"url": url, "headers": headers, "json": json})
        result = {
            "sentences": [
                {
                    "id": "0",
                    "tokens": [
                        {"text": "我", "pinyin": "wǒ"},
                        {"text": "去", "pinyin": "qù"},
                        {"text": "银行", "pinyin": "yínháng"},
                    ],
                },
                {
                    "id": "1",
                    "tokens": [
                        {"text": "这", "pinyin": "zhè"},
                        {"text": "不行", "pinyin": "bùxíng"},
                    ],
                },
            ]
        }
        return FakeResponse({"output_text": json_module.dumps(result, ensure_ascii=False)})


class InvalidClient(FakeClient):
    calls = 0

    async def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
        type(self).calls += 1
        return FakeResponse({"output_text": '{"sentences": []}'})


class FakeFallback(SubtitleNLPProvider):
    calls = 0

    async def analyze_batch(self, texts: list[str]) -> list[list[SubtitleTokenAnalysis]]:
        self.calls += 1
        return [[SubtitleTokenAnalysis(text=text, pinyin="fallback")] for text in texts]


json_module = json


@pytest.mark.asyncio
async def test_openai_subtitle_nlp_returns_contextual_tokens(monkeypatch) -> None:
    FakeClient.requests = []
    monkeypatch.setattr("app.services.subtitle_nlp_service.httpx.AsyncClient", FakeClient)
    provider = OpenAISubtitleNLPProvider(api_key="test-key", model="gpt-test")

    result = await provider.analyze_batch(["我去银行。", "这不行！"])

    assert [[token.text for token in sentence] for sentence in result] == [["我", "去", "银行"], ["这", "不行"]]
    assert result[0][2].pinyin == "yínháng"
    assert result[1][1].pinyin == "bùxíng"
    request = FakeClient.requests[0]
    assert request["url"] == "https://api.openai.com/v1/responses"
    assert request["json"]["text"]["format"]["type"] == "json_schema"
    assert request["json"]["text"]["format"]["strict"] is True


@pytest.mark.asyncio
async def test_openai_subtitle_nlp_retries_then_falls_back(monkeypatch) -> None:
    InvalidClient.calls = 0
    fallback = FakeFallback()
    monkeypatch.setattr("app.services.subtitle_nlp_service.httpx.AsyncClient", InvalidClient)
    monkeypatch.setattr("app.services.subtitle_nlp_service.asyncio.sleep", _no_sleep)
    provider = OpenAISubtitleNLPProvider(api_key="test-key", fallback=fallback)

    result = await provider.analyze_batch(["我去银行。"])

    assert InvalidClient.calls == 2
    assert fallback.calls == 1
    assert result[0][0].pinyin == "fallback"


async def _no_sleep(_: float) -> None:
    return None
