"""Simple in-memory rate limiting utilities for Flask routes."""

from __future__ import annotations

import threading
import time
from collections import deque
from functools import wraps
from typing import Callable

from flask import request

from .responses import api_error


class InMemoryRateLimiter:
    """Fixed-window-ish limiter using timestamp buckets per key."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, bucket_key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            events = self._events.setdefault(bucket_key, deque())
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(1, int(events[0] + window_seconds - now))
                return False, retry_after

            events.append(now)
            return True, 0


_limiter = InMemoryRateLimiter()


def rate_limit(limit: int, window_seconds: int, key_func: Callable[[], str] | None = None, scope: str | None = None):
    """Route decorator that enforces a simple per-key request limit."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            identity_key = key_func() if key_func else (request.remote_addr or "unknown")
            bucket_scope = scope or func.__name__
            allowed, retry_after = _limiter.allow(
                bucket_key=f"{bucket_scope}:{identity_key}",
                limit=limit,
                window_seconds=window_seconds,
            )
            if not allowed:
                return api_error(
                    "Too many requests. Please retry later.",
                    429,
                    error_code="RATE_LIMITED",
                    data={"retry_after_seconds": retry_after},
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator
