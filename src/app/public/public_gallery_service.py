"""In-memory state and helpers for public gallery sharing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class GalleryShareState:
    """Stores share-until timestamp for public gallery access."""

    share_until: datetime | None = None

    def enable(self, minutes: int = 15) -> datetime:
        expires = utcnow() + timedelta(minutes=minutes)
        self.share_until = expires
        return expires

    def is_enabled(self) -> bool:
        return self.share_until is not None and utcnow() < self.share_until

    def remaining_seconds(self) -> int:
        if not self.share_until:
            return 0
        delta = (self.share_until - utcnow()).total_seconds()
        return max(0, int(delta))


@dataclass
class GalleryRateLimiter:
    """Simple per-key rate limiter with 1-minute window."""

    limit_per_minute: int = 30
    window_seconds: int = 60
    buckets: dict[str, tuple[int, datetime]] = field(default_factory=dict)

    def check(self, key: str) -> None:
        now = utcnow()
        count, window_start = self.buckets.get(key, (0, now))
        if (now - window_start).total_seconds() > self.window_seconds:
            count, window_start = 0, now
        if count >= self.limit_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "status": "error",
                    "reason": "rate_limited",
                    "limit_per_minute": self.limit_per_minute,
                },
            )
        self.buckets[key] = (count + 1, window_start)


@dataclass
class GalleryCache:
    """In-memory cache for aggregated gallery payload."""

    ttl_seconds: int = 30
    _data: Any | None = None
    _stored_at: datetime | None = None

    def get(self) -> Any | None:
        if self._data is None or self._stored_at is None:
            return None
        if (utcnow() - self._stored_at).total_seconds() > self.ttl_seconds:
            return None
        return self._data

    def set(self, data: Any) -> None:
        self._data = data
        self._stored_at = utcnow()
