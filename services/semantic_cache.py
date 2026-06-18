import os
import time
import httpx
import logging
from typing import Dict, Tuple

log = logging.getLogger(__name__)

class SemanticCache:
    """In-memory semantic response cache using cosine similarity."""

    def __init__(self, threshold: float = 0.95, maxsize: int = 100):
        self.threshold = threshold
        self.maxsize = maxsize
        # id -> (embedding, response_dict, timestamp)
        self._cache: Dict[str, Tuple[list[float], dict, float]] = {}

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
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
        
        for k, (cached_emb, response, ts) in self._cache.items():
            score = self._cosine_similarity(emb, cached_emb)
            if score > best_score:
                best_score = score
                best_res = response
                
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
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k][2])
            del self._cache[oldest]
            
        key = str(hash(text))
        self._cache[key] = (embedding, response, time.time())

# Global singleton
semantic_cache = SemanticCache()
