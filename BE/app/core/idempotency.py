"""Idempotency keys for write-through creates (PRD Section 13.3: duplicate rapid submits must not
create two items). GitLab has no idempotency header, so Stanley dedupes with a short-lived Redis key.
Fails open if Redis is unreachable: the UI also disables the submit button on first click."""

import logging

import redis.asyncio as redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
TTL_SECONDS = 600
PENDING = "pending"


def _client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


async def claim(key: str) -> str | None:
    """None if this request now owns the key; otherwise the existing value ("pending" or the
    id of the item that request already created)."""
    try:
        client = _client()
        if await client.set(f"idem:{key}", PENDING, nx=True, ex=TTL_SECONDS):
            return None
        return await client.get(f"idem:{key}")
    except redis.RedisError:
        logger.warning("Redis unavailable; skipping idempotency check")
        return None


async def complete(key: str, value: str) -> None:
    try:
        await _client().set(f"idem:{key}", value, ex=TTL_SECONDS)
    except redis.RedisError:
        pass


async def release(key: str) -> None:
    try:
        await _client().delete(f"idem:{key}")
    except redis.RedisError:
        pass
