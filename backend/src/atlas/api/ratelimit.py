"""Tiny in-memory sliding-window rate limiter for public API endpoints.

Per process and per client IP. Good enough for a single-instance demo; not a substitute for
an edge rate limit in a real deployment.
"""

import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

MAX_TRACKED_CLIENTS = 10_000


class RateLimiter:
    """Allow at most `limit` calls per `window_s` seconds for each key."""

    def __init__(
        self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            if len(self._hits) > MAX_TRACKED_CLIENTS:
                self._hits.clear()
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def client_ip(request: Request) -> str:
    """First X-Forwarded-For hop (Render and Vercel sit behind a proxy), else the peer."""
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"
