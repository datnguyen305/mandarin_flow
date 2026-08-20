from fastapi import Header, HTTPException, status

from app.core.config import settings


def get_current_user_id() -> int:
    return settings.default_user_id


def is_valid_dev_token(token: str | None) -> bool:
    return bool(settings.dev_access_token) and token == settings.dev_access_token


def require_dev_access(x_dev_token: str | None = Header(default=None, alias="X-Dev-Token")) -> None:
    if is_valid_dev_token(x_dev_token):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev access is required.")


def has_dev_access(x_dev_token: str | None = Header(default=None, alias="X-Dev-Token")) -> bool:
    return is_valid_dev_token(x_dev_token)
