from __future__ import annotations
import json
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Any
from services.memory_store import BaseMemoryStore

class RedisMemoryStore(BaseMemoryStore):
    """Distributed session memory backed by Redis."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", ttl_days: int = 7) -> None:
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.ttl = timedelta(days=ttl_days)

    def _session_key(self, session_id: str) -> str:
        return f"axon:session:{session_id}"

    def _symbols_key(self, session_id: str) -> str:
        return f"axon:symbols:{session_id}"

    def _schemas_key(self, session_id: str) -> str:
        return f"axon:schemas:{session_id}"

    def _events_key(self, session_id: str) -> str:
        return f"axon:events:{session_id}"

    async def create_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> None:
        key = self._session_key(session_id)
        data = {
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat(),
            "metadata": json.dumps(metadata or {})
        }
        await self.redis.hset(key, mapping=data)
        await self.redis.expire(key, self.ttl)

    async def get_session_symbols(self, session_id: str) -> list[dict[str, Any]]:
        raw = await self.redis.hgetall(self._symbols_key(session_id))
        symbols = []
        for val in raw.values():
            symbols.append(json.loads(val))
        # Redis hash iteration doesn't guarantee order like Symbol ID
        return sorted(symbols, key=lambda x: x.get('symbol_id', 0))

    async def add_session_symbol(
        self, session_id: str, symbol_id: int, qualified_name: str, 
        kind: str, score: float, provenance: str, distance: int
    ) -> None:
        key = self._symbols_key(session_id)
        symbol_data = {
            "symbol_id": symbol_id,
            "qualified_name": qualified_name,
            "kind": kind,
            "score": score,
            "provenance": provenance,
            "distance": distance
        }
        await self.redis.hset(key, qualified_name, json.dumps(symbol_data))
        await self.redis.expire(key, self.ttl)

    async def get_session_schema(self, session_id: str, schema_hash: str) -> dict[str, Any] | None:
        raw = await self.redis.hget(self._schemas_key(session_id), schema_hash)
        return json.loads(raw) if raw else None

    async def cache_session_schema(
        self, session_id: str, schema_hash: str, definition: dict[str, Any], field_names: list[str]
    ) -> None:
        key = self._schemas_key(session_id)
        data = {"definition": definition, "fields": field_names}
        await self.redis.hset(key, schema_hash, json.dumps(data))
        await self.redis.expire(key, self.ttl)

    async def log_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        key = self._events_key(session_id)
        event = {
            "event_type": event_type,
            "payload": payload,
            "created_at": datetime.utcnow().isoformat()
        }
        await self.redis.lpush(key, json.dumps(event))
        await self.redis.ltrim(key, 0, 99) # Keep last 100 events
        await self.redis.expire(key, self.ttl)

    async def get_session_history(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        raw = await self.redis.lrange(self._events_key(session_id), 0, limit - 1)
        return [json.loads(x) for x in raw]

    async def cleanup_old_sessions(self, days: int = 7) -> int:
        # Redis handles this automatically via EXPIRE/TTL
        return 0

    async def session_exists(self, session_id: str) -> bool:
        return await self.redis.exists(self._session_key(session_id)) > 0

    async def delete_session(self, session_id: str) -> None:
        keys = [
            self._session_key(session_id),
            self._symbols_key(session_id),
            self._schemas_key(session_id),
            self._events_key(session_id)
        ]
        await self.redis.delete(*keys)