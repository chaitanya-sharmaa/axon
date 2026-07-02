import asyncio
import hashlib
import json
import logging
import time

log = logging.getLogger(__name__)

class ExactMatchCache:
    """In-memory exact-match cache for LLM requests.
    
    Hashes the full request payload (messages, model, temperature, etc.) and
    stores the exact response to achieve 100% token savings for identical requests.
    
    Thread-safety: mutations are guarded by an asyncio.Lock.
    """

    def __init__(self, maxsize: int = 1000, ttl_seconds: int = 3600):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        # req_hash -> (response_dict, timestamp)
        self._cache: dict[str, tuple[dict, float]] = {}
        self._lock = asyncio.Lock()

    def _compute_hash(self, req_body: dict) -> str:
        """Deterministically serialize and hash the request."""
        # We need a stable JSON serialization, so we sort keys.
        # Ensure we don't mutate the caller's dictionary.
        stable_str = json.dumps(req_body, sort_keys=True)
        return hashlib.sha256(stable_str.encode()).hexdigest()

    async def get(self, req_body: dict) -> dict | None:
        """Retrieve a cached response if an exact match exists."""
        req_hash = self._compute_hash(req_body)

        async with self._lock:
            if req_hash in self._cache:
                response, ts = self._cache[req_hash]
                if time.time() - ts > self.ttl_seconds:
                    # Expired
                    del self._cache[req_hash]
                    return None

                log.info(f"Exact-Match KV Cache hit! Hash: {req_hash[:8]}")
                return response

        return None

    async def set(self, req_body: dict, response: dict):
        """Store a successful LLM response in the exact-match cache."""
        req_hash = self._compute_hash(req_body)

        async with self._lock:
            # Simple eviction: if at capacity, pop a random item
            if len(self._cache) >= self.maxsize and req_hash not in self._cache:
                # In Python 3.7+, dicts maintain insertion order, so this pops the oldest
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[req_hash] = (response, time.time())

# Global singleton for the KV Cache
kv_cache = ExactMatchCache()
