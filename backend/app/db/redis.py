import logging
from collections.abc import AsyncGenerator

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, client: redis.Redis | None) -> None:
        self.client = client

    async def get(self, key: str) -> str | None:
        if self.client is None:
            return None
        try:
            value = await self.client.get(key)
            return value.decode("utf-8") if isinstance(value, bytes) else value
        except Exception as exc:
            logger.warning("Redis get failed for %s: %s", key, exc)
            return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if self.client is None:
            return
        try:
            await self.client.set(key, value, ex=ttl or settings.cache_ttl_seconds)
        except Exception as exc:
            logger.warning("Redis set failed for %s: %s", key, exc)

    async def delete(self, key: str) -> None:
        if self.client is None:
            return
        try:
            await self.client.delete(key)
        except Exception as exc:
            logger.warning("Redis delete failed for %s: %s", key, exc)


async def get_cache() -> AsyncGenerator[RedisCache, None]:
    client: redis.Redis | None = None
    try:
        client = redis.from_url(settings.redis_url)
        await client.ping()
    except Exception as exc:
        logger.warning("Redis unavailable, continuing without cache: %s", exc)
        client = None
    try:
        yield RedisCache(client)
    finally:
        if client is not None:
            await client.aclose()
