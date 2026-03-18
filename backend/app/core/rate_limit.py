import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import HTTPException, status

from app.core.config import settings


class SimpleRateLimiter:
    """
    Very lightweight in-memory rate limiter.
    Scoped per key (e.g. IP or email) and endpoint.
    Note: this is per-process only and intended as a safety net, not a full production limiter.
    """

    def __init__(self):
        # key -> (window_start_ts, count)
        self._counters: Dict[str, Tuple[float, int]] = defaultdict(lambda: (0.0, 0))

    def check(self, key: str, limit_per_minute: int) -> None:
        now = time.time()
        window = 60.0
        window_start, count = self._counters[key]

        if now - window_start > window:
            # Reset window
            self._counters[key] = (now, 1)
            return

        if count >= limit_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait a moment and try again.",
            )

        self._counters[key] = (window_start, count + 1)


login_rate_limiter = SimpleRateLimiter()


def enforce_login_rate_limit(key: str) -> None:
    """
    Enforce a simple rate limit for login-like endpoints.
    Key can be IP, email, or a combination.
    """
    limit = settings.RATE_LIMIT_LOGIN_PER_MINUTE
    if limit <= 0:
        return
    login_rate_limiter.check(key, limit)

