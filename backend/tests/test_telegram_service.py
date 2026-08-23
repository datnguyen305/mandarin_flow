from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.core import config
from app.services import telegram_service
from app.services.telegram_service import TelegramService


class FakeResponse:
    def __init__(self, status_code: int = 200, result: Any = None, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._data = {"ok": status_code < 400, "result": result}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.telegram.org")
            raise httpx.HTTPStatusError("telegram error", request=request, response=httpx.Response(self.status_code, request=request, headers=self.headers))

    def json(self) -> dict[str, Any]:
        return self._data


class FakeClient:
    instances: list["FakeClient"] = []
    responses: list[Any] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.calls = 0
        self.closed = False
        self.__class__.instances.append(self)

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        self.closed = True

    async def post(self, _url: str, json: dict[str, Any]) -> FakeResponse:
        del json
        self.calls += 1
        response = self.__class__.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def configure_settings(monkeypatch: pytest.MonkeyPatch, attempts: int = 3) -> None:
    monkeypatch.setattr(config.settings, "telegram_admin_chat_id", "123")
    monkeypatch.setattr(config.settings, "telegram_max_attempts", attempts)
    monkeypatch.setattr(config.settings, "telegram_retry_backoff_seconds", 0.0)


@pytest.mark.asyncio
async def test_send_message_uses_ipv4_transport_and_closes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch, attempts=1)
    FakeClient.instances = []
    FakeClient.responses = [FakeResponse(result={"message_id": 7})]
    transport_kwargs: dict[str, Any] = {}

    def fake_transport(**kwargs: Any) -> object:
        transport_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", fake_transport)
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    result = await TelegramService("bot-token")._call("sendMessage", {"chat_id": "123", "text": "hello"})

    client = FakeClient.instances[0]
    assert result == {"message_id": 7}
    assert transport_kwargs["local_address"] == "0.0.0.0"
    assert client.kwargs["timeout"].connect == 15.0
    assert client.kwargs["timeout"].read == 30.0
    assert client.closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize("exception_type", [httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout])
async def test_transient_network_errors_retry(monkeypatch: pytest.MonkeyPatch, exception_type: type[Exception]) -> None:
    configure_settings(monkeypatch, attempts=2)
    FakeClient.instances = []
    FakeClient.responses = [exception_type("temporary"), FakeResponse(result={"message_id": 8})]
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(telegram_service.asyncio, "sleep", _no_sleep)

    result = await TelegramService("bot-token")._call("sendMessage", {})

    assert result == {"message_id": 8}
    assert FakeClient.instances[0].calls == 2


@pytest.mark.asyncio
async def test_transient_network_error_stops_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch, attempts=3)
    FakeClient.instances = []
    FakeClient.responses = [httpx.ConnectTimeout("temporary") for _ in range(3)]
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(telegram_service.asyncio, "sleep", _no_sleep)

    result = await TelegramService("bot-token")._call("sendMessage", {})

    assert result is None
    assert FakeClient.instances[0].calls == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401])
async def test_non_recoverable_telegram_errors_are_not_retried(monkeypatch: pytest.MonkeyPatch, status_code: int) -> None:
    configure_settings(monkeypatch, attempts=3)
    FakeClient.instances = []
    FakeClient.responses = [FakeResponse(status_code=status_code)]
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    result = await TelegramService("bot-token")._call("sendMessage", {})

    assert result is None
    assert FakeClient.instances[0].calls == 1


@pytest.mark.asyncio
async def test_rate_limit_retries_with_bounded_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch, attempts=2)
    FakeClient.instances = []
    FakeClient.responses = [FakeResponse(status_code=429, headers={"retry-after": "0"}), FakeResponse(result=True)]
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(telegram_service.asyncio, "sleep", _no_sleep)

    result = await TelegramService("bot-token")._call("answerCallbackQuery", {})

    assert result is True
    assert FakeClient.instances[0].calls == 2


@pytest.mark.asyncio
async def test_unsuccessful_json_response_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch, attempts=1)
    FakeClient.instances = []
    response = FakeResponse(result=None)
    response._data = {"ok": False, "description": "bad request"}
    FakeClient.responses = [response]
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    assert await TelegramService("bot-token")._call("sendMessage", {}) is None


async def _no_sleep(_delay: float) -> None:
    return None
