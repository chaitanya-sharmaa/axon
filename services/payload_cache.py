"""Payload cache for Axon Bridge.

Skips re-encoding identical payloads.  The cache is keyed on the SHA-256
of the canonical JSON representation so equivalent dicts with different key
ordering are treated as the same entry.

The cache is **in-process only** (not distributed).  It is intentionally
small (default 512 entries) — it is a hot-path optimisation for retry
storms and rapid-fire duplicate requests, not a general-purpose cache.

Usage
-----
::

    from services.payload_cache import PayloadCache

    cache = PayloadCache(maxsize=512)
    hit = cache.get(json_text)
    if hit is None:
        hit = expensive_encode(json_text)
        cache.set(json_text, hit)
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Optional


class PayloadCache:
    """Thread-safe LRU cache for encoded payloads, keyed on JSON hash."""

    def __init__(self, maxsize: int = 512) -> None:
        self._maxsize = maxsize
        self._store: OrderedDict[str, str] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def _key(self, json_text: str) -> str:
        return hashlib.sha256(json_text.encode()).hexdigest()

    def get(self, json_text: str) -> Optional[str]:
        """Return the cached encoded string, or ``None`` on a miss."""
        key = self._key(json_text)
        if key in self._store:
            self._store.move_to_end(key)
            self._hits += 1
            return self._store[key]
        self._misses += 1
        return None

    def set(self, json_text: str, encoded: str) -> None:
        """Store *encoded* against the hash of *json_text*."""
        key = self._key(json_text)
        if key in self._store:
            self._store.move_to_end(key)
        else:
            if len(self._store) >= self._maxsize:
                self._store.popitem(last=False)
        self._store[key] = encoded

    def stats(self) -> dict:
        return {
            "size": len(self._store),
            "maxsize": self._maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(
                self._hits / max(1, self._hits + self._misses) * 100, 1
            ),
        }

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0
