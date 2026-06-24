import os
import time
import httpx
import logging
import hashlib
import json
from typing import Dict, Tuple

log = logging.getLogger(__name__)

class SemanticCache:
    """In-memory semantic response cache using cosine similarity on the question and exact match on context."""

    def __init__(self, threshold: float = 0.95, maxsize: int = 100, ttl_seconds: int = 3600):
        self.threshold = threshold
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        # context_hash -> list of (question_text, embedding, norm, response_dict, timestamp)
        self._cache: Dict[str, list[Tuple[str, list[float], float, dict, float]]] = {}
        self._size = 0

    def _fast_cosine(self, a: list[float], norm_a: float, b: list[float], norm_b: float) -> float:
        if norm_a == 0 or norm_b == 0:
            return 0.0
        dot = sum(a[i] * b[i] for i in range(len(a)))
        return dot / (norm_a * norm_b)

    def _extract_context_and_question(self, messages: list[dict]) -> tuple[str, str]:
        if not messages:
            return "", ""
        if messages[-1].get("role") == "user":
            question = str(messages[-1].get("content", ""))
            context_msgs = messages[:-1]
        else:
            question = ""
            context_msgs = messages
            
        context_str = json.dumps(context_msgs, sort_keys=True)
        context_hash = hashlib.sha256(context_str.encode()).hexdigest()
        return context_hash, question

    async def get_embedding(self, text: str, api_key: str) -> list[float] | None:
        """Fetch an embedding from the upstream provider."""
        if not text.strip():
            return None
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

    async def check_cache(self, messages: list[dict], api_key: str) -> Tuple[dict | None, dict | None]:
        """Check if a semantically similar prompt exists for this context. Returns (response, state_dict)."""
        if not messages:
            return None, None
            
        context_hash, question = self._extract_context_and_question(messages)
        if not question:
            return None, None
            
        # We only need to embed if the context exists in cache
        if context_hash not in self._cache or not self._cache[context_hash]:
            # To save embedding API costs, don't embed if we have zero cache hits for this context
            emb = await self.get_embedding(question, api_key)
            return None, {"context_hash": context_hash, "question": question, "embedding": emb}
            
        emb = await self.get_embedding(question, api_key)
        state_dict = {"context_hash": context_hash, "question": question, "embedding": emb}
        if not emb:
            return None, state_dict
            
        best_score = -1.0
        best_res = None
        now = time.time()
        
        norm_a = sum(x * x for x in emb) ** 0.5
        valid_entries = []
        
        for q_text, cached_emb, cached_norm, response, ts in self._cache[context_hash]:
            if now - ts > self.ttl_seconds:
                self._size -= 1
                continue
                
            valid_entries.append((q_text, cached_emb, cached_norm, response, ts))
            score = self._fast_cosine(emb, norm_a, cached_emb, cached_norm)
            if score > best_score:
                best_score = score
                best_res = response
                
        self._cache[context_hash] = valid_entries
        if not valid_entries:
            del self._cache[context_hash]
                
        if best_score >= self.threshold:
            log.info(f"Semantic cache hit! Similarity: {best_score:.3f}")
            return best_res, state_dict
            
        return None, state_dict

    def store_response(self, state_dict: dict | None, response: dict):
        """Store a successful LLM response in the cache."""
        if not state_dict or not response:
            return
            
        context_hash = state_dict.get("context_hash")
        question = state_dict.get("question")
        embedding = state_dict.get("embedding")
        
        if not context_hash or not question or not embedding:
            return
            
        if self._size >= self.maxsize:
            # Simple eviction: clear oldest context completely to free space
            if self._cache:
                oldest_ctx = list(self._cache.keys())[0]
                self._size -= len(self._cache[oldest_ctx])
                del self._cache[oldest_ctx]
            
        if context_hash not in self._cache:
            self._cache[context_hash] = []
            
        norm = sum(x * x for x in embedding) ** 0.5
        self._cache[context_hash].append((question, embedding, norm, response, time.time()))
        self._size += 1

# Global singleton
semantic_cache = SemanticCache()
