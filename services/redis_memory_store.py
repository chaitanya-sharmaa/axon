from __future__ import annotations
import json
import redis.asyncio as redis
from datetime import datetime, timedelta, timezone
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

    def _facts_key(self, session_id: str) -> str:
        return f"axon:facts:{session_id}"

    async def create_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> None:
        key = self._session_key(session_id)
        data = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_accessed": datetime.now(timezone.utc).isoformat(),
            "metadata": json.dumps(metadata or {})
        }
        await self.redis.hset(key, mapping=data)  # type: ignore
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
            "created_at": datetime.now(timezone.utc).isoformat()
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
            self._events_key(session_id),
            self._facts_key(session_id)
        ]
        await self.redis.delete(*keys)

    async def list_all_sessions(self) -> list[dict[str, Any]]:
        # For Redis, we can scan keys matching axon:session:* 
        # But for tests, returning an empty list or scanning is fine.
        keys = await self.redis.keys("axon:session:*")
        sessions = []
        for k in keys:
            data = await self.redis.hgetall(k)
            k_str = k.decode('utf-8') if isinstance(k, bytes) else k
            # Decode values in data to match the expected dict[str, Any]
            decoded_data = {
                (k_attr.decode('utf-8') if isinstance(k_attr, bytes) else k_attr): 
                (v_attr.decode('utf-8') if isinstance(v_attr, bytes) else v_attr)
                for k_attr, v_attr in data.items()
            }
            sessions.append({"session_id": k_str.replace("axon:session:", ""), **decoded_data})
        return sessions

    async def add_session_fact(self, session_id: str, fact: str) -> None:
        key = self._facts_key(session_id)
        # using sadd to automatically enforce uniqueness
        await self.redis.sadd(key, fact)
        await self.redis.expire(key, self.ttl)

    async def get_session_facts(self, session_id: str) -> list[str]:
        key = self._facts_key(session_id)
        facts = await self.redis.smembers(key)
        return [f.decode('utf-8') if isinstance(f, bytes) else f for f in facts]

    # ── Tenant Quotas ─────────────────────────────────────────────────────────

    async def get_tenant_quota(self, tenant_id: str) -> tuple[float, float]:
        key = f"axon:tenant:{tenant_id}"
        result = await self.redis.hmget(key, "quota_usd", "spend_usd")
        quota = float(result[0]) if result[0] is not None else 0.0
        spend = float(result[1]) if result[1] is not None else 0.0
        return quota, spend

    async def set_tenant_quota(self, tenant_id: str, quota_usd: float) -> None:
        key = f"axon:tenant:{tenant_id}"
        # Set quota, and initialize spend to 0.0 only if it doesn't exist
        await self.redis.hset(key, "quota_usd", str(quota_usd))
        await self.redis.hsetnx(key, "spend_usd", "0.0")

    async def increment_tenant_spend(self, tenant_id: str, cost_usd: float) -> None:
        if cost_usd > 0:
            key = f"axon:tenant:{tenant_id}"
            await self.redis.hincrbyfloat(key, "spend_usd", cost_usd)

    # ── Thread Management ─────────────────────────────────────────────────────

    def _thread_key(self, session_id: str) -> str:
        return f"axon:thread:{session_id}"

    async def get_thread(self, session_id: str) -> list[dict[str, Any]]:
        key = self._thread_key(session_id)
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return []

    async def append_to_thread(self, session_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        key = self._thread_key(session_id)
        # We need a small transaction/lock to read-append-write safely in Redis
        # For simplicity in this demo, we'll just get and set
        data = await self.redis.get(key)
        history = json.loads(data) if data else []
        history.extend(messages)
        await self.redis.set(key, json.dumps(history))
        await self.redis.expire(key, self.ttl)
        return history