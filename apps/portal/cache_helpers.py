"""Shared-cache helpers for stampede protection and short-lived build locks."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from django.core.cache import cache

T = TypeVar("T")


def cache_get_or_set_locked(
    key: str,
    builder: Callable[[], T],
    timeout: int,
    *,
    lock_seconds: int = 15,
) -> T:
    """
    Return cached value or build once under a short lock (avoids thundering herd).
    """
    value = cache.get(key)
    if value is not None:
        return value

    lock_key = f"{key}:lock"
    if cache.add(lock_key, 1, lock_seconds):
        try:
            value = cache.get(key)
            if value is not None:
                return value
            value = builder()
            cache.set(key, value, timeout)
            return value
        finally:
            cache.delete(lock_key)

    value = cache.get(key)
    if value is not None:
        return value
    return builder()


def try_portal_build_lock(scope: str, student_id: int, *, ttl: int = 45) -> bool:
    """True when this worker may build a heavy portal page for the learner."""
    return cache.add(f"portal:build:{scope}:{student_id}", 1, ttl)


def release_portal_build_lock(scope: str, student_id: int) -> None:
    cache.delete(f"portal:build:{scope}:{student_id}")
