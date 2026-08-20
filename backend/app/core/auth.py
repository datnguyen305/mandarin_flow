import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models import GuestSession


async def get_or_create_guest(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> GuestSession:
    now = datetime.now(UTC)
    raw_token = request.cookies.get(settings.guest_cookie_name)
    guest = None
    if raw_token:
        result = await db.execute(
            select(GuestSession).where(
                GuestSession.token_hash == _hash_token(raw_token),
                GuestSession.expires_at > now,
            )
        )
        guest = result.scalar_one_or_none()

    if guest is None:
        raw_token = secrets.token_urlsafe(32)
        guest = GuestSession(
            token_hash=_hash_token(raw_token),
            last_seen_at=now,
            expires_at=now + timedelta(days=settings.guest_session_days),
        )
        db.add(guest)
        await db.commit()
        await db.refresh(guest)
        response.set_cookie(
            key=settings.guest_cookie_name,
            value=raw_token,
            max_age=settings.guest_session_days * 86400,
            httponly=True,
            secure=settings.environment == "production",
            samesite="lax",
            path="/",
        )
    elif now - guest.last_seen_at > timedelta(days=1):
        guest.last_seen_at = now
        await db.commit()

    return guest


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_valid_dev_token(token: str | None) -> bool:
    return bool(settings.dev_access_token) and token == settings.dev_access_token


def require_dev_access(x_dev_token: str | None = Header(default=None, alias="X-Dev-Token")) -> None:
    if is_valid_dev_token(x_dev_token):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev access is required.")


def has_dev_access(x_dev_token: str | None = Header(default=None, alias="X-Dev-Token")) -> bool:
    return is_valid_dev_token(x_dev_token)
