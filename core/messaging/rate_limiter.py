"""Async time-based rate limiter for outbound requests."""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Ensure a minimum delay between calls across concurrent tasks."""

    def __init__(self, min_delay_ms: int) -> None:
        self._min_delay_s = max(0, min_delay_ms) / 1000.0
        self._lock = asyncio.Lock()
        self._last_request_ts = 0.0

    async def wait(self) -> None:
        """Sleep until the minimum delay since the last request has elapsed."""
        if self._min_delay_s <= 0:
            return

        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_ts
            delay = self._min_delay_s - elapsed
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request_ts = time.monotonic()
