import json

import pytest

from app.services.video_topic_classifier import OpenAIVideoTopicClassifier, _subtitle_sample


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


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
        return FakeResponse(
            {
                "output_text": json_module.dumps(
                    {
                        "primary_topic": "Du lịch",
                        "secondary_topics": ["Ẩm thực", "Đời sống"],
                        "confidence": 0.92,
                    },
                    ensure_ascii=False,
                )
            }
        )


class InvalidClient(FakeClient):
    calls = 0

    async def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
        type(self).calls += 1
        return FakeResponse({"output_text": '{"primary_topic":"HSK1"}'})


json_module = json


@pytest.mark.asyncio
async def test_openai_classifier_uses_closed_topic_schema(monkeypatch) -> None:
    FakeClient.requests = []
    monkeypatch.setattr("app.services.video_topic_classifier.httpx.AsyncClient", FakeClient)
    classifier = OpenAIVideoTopicClassifier(api_key="test-key", model="gpt-test")

    result = await classifier.classify("Một ngày ở Thành Đô", ["我们先去吃火锅。", "下午参观博物馆。"])

    assert result == ["Du lịch", "Ẩm thực", "Đời sống"]
    request = FakeClient.requests[0]
    assert request["url"] == "https://api.openai.com/v1/responses"
    assert request["json"]["text"]["format"]["type"] == "json_schema"
    assert request["json"]["text"]["format"]["strict"] is True
    assert "HSK level" in request["json"]["instructions"]


@pytest.mark.asyncio
async def test_invalid_classification_retries_once_then_returns_empty(monkeypatch) -> None:
    InvalidClient.calls = 0
    monkeypatch.setattr("app.services.video_topic_classifier.httpx.AsyncClient", InvalidClient)
    monkeypatch.setattr("app.services.video_topic_classifier.asyncio.sleep", _no_sleep)
    classifier = OpenAIVideoTopicClassifier(api_key="test-key")

    result = await classifier.classify("HSK1 lesson", ["你好"])

    assert result == []
    assert InvalidClient.calls == 2


@pytest.mark.asyncio
async def test_missing_api_key_degrades_without_request(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("OpenAI should not be called without an API key")

    monkeypatch.setattr("app.services.video_topic_classifier.httpx.AsyncClient", fail_if_called)
    classifier = OpenAIVideoTopicClassifier(api_key=None)
    classifier.api_key = None

    assert await classifier.classify("Video", ["你好"]) == []


def test_subtitle_sample_limits_lines_and_characters() -> None:
    sample = _subtitle_sample(["  第一行  ", *["字" * 300 for _ in range(30)]])

    assert sample[0] == "第一行"
    assert len(sample) <= 20
    assert sum(map(len, sample)) <= 4000


async def _no_sleep(_: float) -> None:
    return None
