import pytest

from app.services.translation_service import OpenAITranslationProvider


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeAsyncClient:
    requests: list[dict] = []

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
        self.requests.append({"url": url, "headers": headers, "json": json})
        return FakeResponse({"output_text": '["Nhìn người bạn Nhật Bản của cô ấy, Yamamoto."]'})


class LengthMismatchThenSingleLineClient:
    requests: list[dict] = []
    responses = [
        {"output_text": '["Dòng một"]'},
        {"output_text": '["Dòng một"]'},
        {"output_text": '["Dòng hai"]'},
    ]

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "LengthMismatchThenSingleLineClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
        self.requests.append({"url": url, "headers": headers, "json": json})
        return FakeResponse(self.responses.pop(0))


class MalformedSingleLineClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "MalformedSingleLineClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
        return FakeResponse({"output_text": "not json"})


@pytest.mark.asyncio
async def test_openai_translation_provider_translates_batch(monkeypatch) -> None:
    FakeAsyncClient.requests = []
    monkeypatch.setattr("app.services.translation_service.httpx.AsyncClient", FakeAsyncClient)
    provider = OpenAITranslationProvider(api_key="test-key", model="gpt-test")

    translations = await provider.translate_batch(["看她的日本朋友山本。"], "zh", "vi")

    assert translations == ["Nhìn người bạn Nhật Bản của cô ấy, Yamamoto."]
    request = FakeAsyncClient.requests[0]
    assert request["url"] == "https://api.openai.com/v1/responses"
    assert request["headers"]["Authorization"] == "Bearer test-key"
    assert request["json"]["model"] == "gpt-test"
    assert "看她的日本朋友山本。" in request["json"]["input"]


@pytest.mark.asyncio
async def test_openai_translation_provider_recovers_from_batch_length_mismatch(monkeypatch) -> None:
    LengthMismatchThenSingleLineClient.requests = []
    LengthMismatchThenSingleLineClient.responses = [
        {"output_text": '["Dòng một"]'},
        {"output_text": '["Dòng một"]'},
        {"output_text": '["Dòng hai"]'},
    ]
    monkeypatch.setattr("app.services.translation_service.httpx.AsyncClient", LengthMismatchThenSingleLineClient)
    provider = OpenAITranslationProvider(api_key="test-key", model="gpt-test")

    translations = await provider.translate_batch(["第一行。", "第二行。"], "zh", "vi")

    assert translations == ["Dòng một", "Dòng hai"]
    assert len(LengthMismatchThenSingleLineClient.requests) == 3


@pytest.mark.asyncio
async def test_openai_translation_provider_falls_back_for_bad_single_line_response(monkeypatch) -> None:
    monkeypatch.setattr("app.services.translation_service.httpx.AsyncClient", MalformedSingleLineClient)
    provider = OpenAITranslationProvider(api_key="test-key", model="gpt-test")

    translations = await provider.translate_batch(["第一行。"], "zh", "vi")

    assert translations == ["[vi] 第一行。"]


@pytest.mark.parametrize(
    ("output_text", "expected"),
    [
        ('["Xin chào."]', ["Xin chào."]),
        ('```json\n["Xin chào."]\n```', ["Xin chào."]),
        ('Đây là bản dịch:\n["Xin chào."]', ["Xin chào."]),
    ],
)
def test_openai_translation_provider_parses_json_array_from_common_response_shapes(output_text: str, expected: list[str]) -> None:
    provider = OpenAITranslationProvider(api_key="test-key", model="gpt-test")

    assert provider._parse_translation_array(output_text) == expected
