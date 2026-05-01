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


# ---------------------------------------------------------------------------
# JTI helpers
# ---------------------------------------------------------------------------

def _jti_key(jti: str) -> str:
    return f"jti:{jti}"


def _user_jtis_key(user_id: str) -> str:
    return f"user_jtis:{user_id}"


async def store_jti(jti: str, ttl_seconds: int, user_id: Optional[str] = None) -> None:
    r = await get_redis()
    await r.set(_jti_key(jti), user_id or "1", ex=ttl_seconds)
    if user_id:
        ukey = _user_jtis_key(user_id)
        await r.sadd(ukey, jti)
        # Keep the set alive at least as long as the longest token
        current_ttl = await r.ttl(ukey)
        if current_ttl < ttl_seconds:
            await r.expire(ukey, ttl_seconds)


async def revoke_jti(jti: str) -> None:
    r = await get_redis()
    await r.delete(_jti_key(jti))


async def is_jti_valid(jti: str) -> bool:
    r = await get_redis()
    return await r.exists(_jti_key(jti)) == 1


async def revoke_all_user_jtis(user_id: str) -> None:
    """Invalidate every active access/refresh JTI for the given user."""
    r = await get_redis()
    ukey = _user_jtis_key(user_id)
    jtis = await r.smembers(ukey)
    if jtis:
        await r.delete(*[_jti_key(j) for j in jtis])
    await r.delete(ukey)


# ---------------------------------------------------------------------------
# Email-verification token helpers
# ---------------------------------------------------------------------------

_EMAIL_VERIFY_TTL = 86400  # 24 hours


def _email_verify_key(token: str) -> str:
    return f"email_verify:{token}"


async def store_email_verify_token(token: str, user_id: str) -> None:
    r = await get_redis()
    await r.set(_email_verify_key(token), user_id, ex=_EMAIL_VERIFY_TTL)


async def get_email_verify_token(token: str) -> Optional[str]:
    r = await get_redis()
    return await r.get(_email_verify_key(token))


async def delete_email_verify_token(token: str) -> None:
    r = await get_redis()
    await r.delete(_email_verify_key(token))


# ---------------------------------------------------------------------------
# Password-reset token helpers
# ---------------------------------------------------------------------------

_PWD_RESET_TTL = 1800  # 30 minutes (SR1)


def _pwd_reset_key(token: str) -> str:
    return f"pwd_reset:{token}"


async def store_pwd_reset_token(token: str, user_id: str) -> None:
    r = await get_redis()
    await r.set(_pwd_reset_key(token), user_id, ex=_PWD_RESET_TTL)


async def get_pwd_reset_token(token: str) -> Optional[str]:
    r = await get_redis()
    return await r.get(_pwd_reset_key(token))


async def delete_pwd_reset_token(token: str) -> None:
    r = await get_redis()
    await r.delete(_pwd_reset_key(token))
