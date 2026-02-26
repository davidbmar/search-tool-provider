"""Shared utilities: score normalization, dedup, HTML cleaning, TTL cache."""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from typing import Any

from .models import SearchResult

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_scores(results: list[SearchResult]) -> list[SearchResult]:
    """Normalize result scores to 0.0–1.0 range.

    If scores are already in range, keeps them. If all zero,
    assigns position-based scores: 1.0 - (position / (n + 1)).
    Otherwise scales linearly to [0, 1].
    """
    if not results:
        return results

    scores = [r.score for r in results]
    max_score = max(scores)
    min_score = min(scores)

    # All zero → position-based
    if max_score == 0:
        n = len(results)
        for i, r in enumerate(results):
            r.score = round(1.0 - (i / (n + 1)), 4)
        return results

    # Already in [0, 1]
    if 0 <= min_score and max_score <= 1.0:
        return results

    # Scale to [0, 1]
    spread = max_score - min_score
    if spread == 0:
        for r in results:
            r.score = 1.0
    else:
        for r in results:
            r.score = round((r.score - min_score) / spread, 4)
    return results


def deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    """Remove duplicate results by URL, keeping the first occurrence."""
    seen: set[str] = set()
    deduped: list[SearchResult] = []
    for r in results:
        url = r.url.rstrip("/")
        if url not in seen:
            seen.add(url)
            deduped.append(r)
    return deduped


def clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not text:
        return text
    text = _TAG_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


class TTLCache:
    """Async-safe in-memory cache with time-to-live expiration.

    Args:
        ttl: Time-to-live in seconds (default 300).
        max_size: Maximum number of cached entries (default 100).
    """

    def __init__(self, ttl: float = 300, max_size: int = 100) -> None:
        self.ttl = ttl
        self.max_size = max_size
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _make_key(query: str, max_results: int, **kwargs: Any) -> str:
        """Create a cache key from query parameters."""
        raw = f"{query}|{max_results}|{sorted(kwargs.items())}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def get(self, key: str) -> Any | None:
        """Get a cached value, or None if expired / missing."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.monotonic() - ts > self.ttl:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any) -> None:
        """Store a value in the cache."""
        async with self._lock:
            # Evict oldest if full
            if len(self._store) >= self.max_size and key not in self._store:
                oldest_key = min(self._store, key=lambda k: self._store[k][0])
                del self._store[oldest_key]
            self._store[key] = (time.monotonic(), value)

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._store.clear()
