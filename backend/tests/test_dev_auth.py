import pytest
from fastapi import HTTPException

from app.core.auth import has_dev_access, require_dev_access
from app.core.config import settings


def test_require_dev_access_rejects_missing_or_invalid_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dev_access_token", "secret")

    with pytest.raises(HTTPException) as missing:
        require_dev_access()
    with pytest.raises(HTTPException) as invalid:
        require_dev_access("wrong")
    assert missing.value.status_code == 403
    assert invalid.value.status_code == 403


def test_require_dev_access_accepts_valid_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dev_access_token", "secret")

    assert require_dev_access("secret") is None


def test_has_dev_access_is_false_when_secret_is_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dev_access_token", None)

    assert has_dev_access("secret") is False
