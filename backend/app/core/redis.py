from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _jti_key(jti: str) -> str:
    return f"jti:{jti}"


async def store_jti(jti: str, ttl_seconds: int) -> None:
    """Persist a JTI in Redis so it can be validated later."""
    r = await get_redis()
    await r.set(_jti_key(jti), "1", ex=ttl_seconds)


async def revoke_jti(jti: str) -> None:
    """Delete a JTI from Redis, effectively revoking that token."""
    r = await get_redis()
    await r.delete(_jti_key(jti))


async def is_jti_valid(jti: str) -> bool:
    """Return True only if the JTI key still exists (not revoked, not expired)."""
    r = await get_redis()
    return await r.exists(_jti_key(jti)) == 1
