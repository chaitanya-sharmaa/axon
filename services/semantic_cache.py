import os
import time
import httpx
import logging
from typing import Dict, Tuple

log = logging.getLogger(__name__)

class SemanticCache:
    """In-memory semantic response cache using cosine similarity."""

    def __init__(self, threshold: float = 0.95, maxsize: int = 100, ttl_seconds: int = 3600):
        self.threshold = threshold
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        # id -> (embedding, norm, response_dict, timestamp)
        self._cache: Dict[str, Tuple[list[float], float, dict, float]] = {}

    def _fast_cosine(self, a: list[float], norm_a: float, b: list[float], norm_b: float) -> float:
        if norm_a == 0 or norm_b == 0:
            return 0.0
        # Inline the dot product loop for speed
        dot = sum(a[i] * b[i] for i in range(len(a)))
        return dot / (norm_a * norm_b)

    async def get_embedding(self, text: str, api_key: str) -> list[float] | None:
        """Fetch an embedding from the upstream provider."""
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY", "")
            
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{base_url}/embeddings",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"input": text, "model": "text-embedding-3-small"}
                )
                if resp.status_code == 200:
                    return resp.json()["data"][0]["embedding"]
            except Exception as e:
                log.warning(f"Failed to get embedding for cache: {e}")
        return None

    async def check_cache(self, text: str, api_key: str) -> Tuple[dict | None, list[float] | None]:
        """Check if a semantically similar prompt exists. Returns (response, embedding)."""
        if not text.strip():
            return None, None
            
        emb = await self.get_embedding(text, api_key)
        if not emb:
            return None, None
            
        if not self._cache:
            return None, emb
            
        best_score = -1.0
        best_res = None
        now = time.time()
        expired_keys = []
        
        # Precompute norm_a once for this request
        norm_a = sum(x * x for x in emb) ** 0.5
        
        for k, (cached_emb, cached_norm, response, ts) in self._cache.items():
            if now - ts > self.ttl_seconds:
                expired_keys.append(k)
                continue
                
            score = self._fast_cosine(emb, norm_a, cached_emb, cached_norm)
            if score > best_score:
                best_score = score
                best_res = response
                
        for k in expired_keys:
            del self._cache[k]
                
        if best_score >= self.threshold:
            log.info(f"Semantic cache hit! Similarity: {best_score:.3f}")
            return best_res, emb
            
        return None, emb

    def store_response(self, text: str, embedding: list[float], response: dict):
        """Store a successful LLM response in the cache."""
        if not embedding or not response:
            return
            
        if len(self._cache) >= self.maxsize:
            # Evict oldest
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k][3])
            del self._cache[oldest]
            
        key = str(hash(text))
        norm = sum(x * x for x in embedding) ** 0.5
        self._cache[key] = (embedding, norm, response, time.time())

# Global singleton
semantic_cache = SemanticCache()
