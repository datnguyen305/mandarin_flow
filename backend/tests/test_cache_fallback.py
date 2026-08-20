import pytest

from app.db.redis import RedisCache


class BrokenClient:
    async def get(self, key: str) -> str:
        raise RuntimeError("redis down")

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        raise RuntimeError("redis down")


@pytest.mark.asyncio
async def test_redis_cache_falls_back_to_none_when_unavailable() -> None:
    cache = RedisCache(BrokenClient())  # type: ignore[arg-type]
    assert await cache.get("video:abc:subtitles:zh-vi") is None
    await cache.set("video:abc:subtitles:zh-vi", "{}")
