"""Redis-backed sliding-window rate limiter.

Uses per-key atomic INCR with a fixed window + EXPIRE. Falls back gracefully to
"allow" when Redis is unavailable so transient cache outages never block the
application — rate limiting must not become a new failure point.
"""

from __future__ import annotations

from pricepilot.logging import get_logger

log = get_logger("rate_limit")


class RateLimiter:
    def __init__(self, redis: object | None) -> None:
        self.redis = redis
        self._unavailable_logged = False

    async def check_or_increment(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """Return (allowed, current_count_in_window)."""
        if self.redis is None:
            return self._allow_unavailable(key)

        try:
            value = await self.redis.incr(key)
        except Exception:
            return self._allow_unavailable(key)

        if value == 1:
            try:
                await self.redis.expire(key, window_seconds)
            except Exception:
                return self._allow_unavailable(key)

        if value > limit:
            return False, int(value)
        return True, int(value)

    def _allow_unavailable(self, key: str) -> tuple[bool, int]:
        if not self._unavailable_logged:
            log.warning("Redis unreachable; rate limiting disabled for key %s", key)
            self._unavailable_logged = True
        return True, 0