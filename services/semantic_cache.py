import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import orjson

from core.app_config import memory_store

log = logging.getLogger(__name__)

class SemanticCache:
    """Persistent semantic response cache using cosine similarity on the question and exact match on context.
    
    Data is stored in the universal `memory_store` (libSQL/Turso), allowing serverless 
    instances and cross-region nodes to share the cache seamlessly.
    """

    def __init__(self, threshold: float = 0.95, maxsize: int = 100, ttl_seconds: int = 3600):
        self.threshold = threshold
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds

    def _fast_cosine(self, a: list[float], norm_a: float, b: list[float], norm_b: float) -> float:
        if norm_a == 0 or norm_b == 0:
            return 0.0
        dot = float(np.dot(a, b))
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

        context_bytes = orjson.dumps(context_msgs, option=orjson.OPT_SORT_KEYS)
        context_hash = hashlib.sha256(context_bytes).hexdigest()
        return context_hash, question

    async def get_embedding(self, text: str, api_key: str) -> list[float] | None:
        """Fetch an embedding using the local fastembed engine."""
        if not text.strip():
            return None

        try:
            from services.intent_classifier import get_embedder
            embedder = get_embedder()
            if embedder:
                emb = list(embedder.embed([text]))[0]
                return emb.tolist()
        except Exception as e:
            log.warning(f"Failed to get local embedding for cache: {e}")
        return None

    async def check_cache(self, messages: list[dict], api_key: str) -> tuple[dict | None, dict | None]:
        """Check if a semantically similar prompt exists for this context. Returns (response, state_dict)."""
        if not messages:
            return None, None

        context_hash, question = self._extract_context_and_question(messages)
        if not question:
            return None, None

        emb = await self.get_embedding(question, api_key)
        state_dict = {"context_hash": context_hash, "question": question, "embedding": emb}
        if not emb:
            return None, state_dict

        # Fetch candidate entries from the database
        cutoff_iso = (datetime.now(timezone.utc) - timedelta(seconds=self.ttl_seconds)).isoformat()

        # Ensure memory_store supports Semantic Cache features
        if not hasattr(memory_store, "get_active_semantic_cache"):
            log.warning("memory_store does not support get_active_semantic_cache (Redis config?). Skipping cache.")
            return None, state_dict

        rows = await memory_store.get_active_semantic_cache(context_hash, cutoff_iso, limit=self.maxsize)

        best_score = -1.0
        best_res = None
        norm_a = sum(x * x for x in emb) ** 0.5

        for row in rows:
            try:
                cached_emb = orjson.loads(row["embedding"])
                cached_norm = sum(x * x for x in cached_emb) ** 0.5
                score = self._fast_cosine(emb, norm_a, cached_emb, cached_norm)
                if score > best_score:
                    best_score = score
                    best_res = orjson.loads(row["response_json"])
            except Exception as e:
                log.warning(f"Failed to parse cached vector: {e}")

        if best_score >= self.threshold:
            log.info(f"Semantic cache hit! Similarity: {best_score:.3f}")
            return best_res, state_dict

        return None, state_dict

    async def store_response(self, state_dict: dict | None, response: dict):
        """Store a successful LLM response in the cache database."""
        if not state_dict or not response:
            return

        context_hash = state_dict.get("context_hash")
        question = state_dict.get("question")
        embedding = state_dict.get("embedding")

        if not context_hash or not question or not embedding:
            return

        if hasattr(memory_store, "store_semantic_cache"):
            # Fire and forget storage into DB
            await memory_store.store_semantic_cache(context_hash, question, embedding, response)

    async def get_all_entries(self) -> list[dict]:
        """Return a snapshot of all cache entries."""
        if hasattr(memory_store, "get_all_semantic_cache_entries"):
            cutoff_iso = (datetime.now(timezone.utc) - timedelta(seconds=self.ttl_seconds)).isoformat()
            rows = await memory_store.get_all_semantic_cache_entries(cutoff_iso)
            entries = []
            for row in rows:
                # Convert ISO string to unix timestamp for backward compatibility with dashboard
                try:
                    dt = datetime.fromisoformat(row["created_at"].replace('Z', '+00:00'))
                    ts = dt.timestamp()
                except Exception:
                    ts = time.time()
                entries.append({
                    "context_hash": row["context_hash"],
                    "question": row["question"],
                    "timestamp": ts,
                })
            return entries
        return []

# Global singleton
semantic_cache = SemanticCache()
