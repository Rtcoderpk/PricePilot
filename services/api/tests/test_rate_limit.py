"""Unit tests for the Redis-backed rate limiter (uses fakeredis → an in-memory
Redis that satisfies redis-py's async calls without a server)."""

from __future__ import annotations

from pricepilot.rate_limit import RateLimiter


class _FakeRedis:
    """Tiny Redis stand-in for the limiter's INCR/EXPIRE surface."""

    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def expire(self, key: str, ttl: int) -> None:
        return None


async def test_allows_up_to_limit() -> None:
    limiter = RateLimiter(_FakeRedis())
    for _ in range(5):
        allowed, count = await limiter.check_or_increment("k", limit=5, window_seconds=60)
        assert allowed is True
        assert count <= 5


async def test_blocks_over_limit() -> None:
    limiter = RateLimiter(_FakeRedis())
    for _ in range(5):
        await limiter.check_or_increment("k", limit=5, window_seconds=60)
    allowed, count = await limiter.check_or_increment("k", limit=5, window_seconds=60)
    assert allowed is False
    assert count == 6


async def test_allows_when_redis_none() -> None:
    limiter = RateLimiter(None)
    allowed, count = await limiter.check_or_increment("k", limit=1, window_seconds=60)
    assert allowed is True
    assert count == 0