"""Persistent session memory for Axon bridge with schema caching and symbol tracking."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from services.memory_store import BaseMemoryStore
import libsql_client

log = logging.getLogger(__name__)


class LibsqlMemoryStore(BaseMemoryStore):
    """Persistent session memory backed by Turso (libSQL) or local SQLite.

    Key features:
    * **Unified Engine**: Works seamlessly with local SQLite files (file:./db.sqlite)
      and remote Turso Edge databases (libsql://...) using the same driver.
    * **ON DELETE CASCADE** — deleting a session row automatically removes all
      child rows (symbols, schemas, events), so ``delete_session`` and
      ``cleanup_old_sessions`` only need to touch one table.
    * **Auto-Commit**: libsql-client handles single-statement transactions automatically.
    """

    def __init__(self, url: str = "file:./axon_sessions.db", auth_token: str | None = None) -> None:
        self.url = url
        self.auth_token = auth_token
        self._lock: asyncio.Lock | None = None
        self._client: libsql_client.Client | None = None

    @property
    def lock(self) -> asyncio.Lock:
        assert self._lock is not None, "MemoryStore not initialized"
        return self._lock

    # ── Connection management ──────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Explicitly open the database connection on the current event loop."""
        await self._ensure_conn()

    async def _ensure_conn(self) -> libsql_client.Client:
        """Return (or lazily create) the shared persistent connection."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        
        if self._client is None:
            self._client = libsql_client.create_client(self.url, auth_token=self.auth_token)
            
            # Pragma execution (only run if local file, remote Turso doesn't need/allow PRAGMA journal_mode)
            if self.url.startswith("file:"):
                try:
                    await self._client.execute("PRAGMA journal_mode=WAL")
                    await self._client.execute("PRAGMA foreign_keys=ON")
                    await self._client.execute("PRAGMA wal_checkpoint(PASSIVE)")
                except Exception as e:
                    log.warning(f"Failed to set PRAGMAs on local db (this is safe to ignore for remote Turso): {e}")

            await self._init_schema(self._client)
        return self._client

    async def close(self) -> None:
        """Close the persistent connection (call this on app shutdown)."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            log.debug("libSQL connection closed.")

    # ── Schema initialisation ──────────────────────────────────────────────────

    async def _init_schema(self, client: libsql_client.Client) -> None:
        """Create tables if they don't already exist.
        libSQL batch execution is the safest way to initialize.
        """
        statements = [
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TIMESTAMP,
                last_accessed TIMESTAMP,
                metadata TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS session_symbols (
                session_id TEXT,
                symbol_id INTEGER,
                qualified_name TEXT,
                kind TEXT,
                score REAL,
                provenance TEXT,
                distance INTEGER,
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
                PRIMARY KEY (session_id, qualified_name)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS session_schemas (
                session_id TEXT,
                schema_hash TEXT,
                schema_definition TEXT,
                field_names TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
                PRIMARY KEY (session_id, schema_hash)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS memory_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                event_type TEXT,
                payload TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS session_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                fact TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
                UNIQUE (session_id, fact)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tenant_quotas (
                tenant_id TEXT PRIMARY KEY,
                quota_usd REAL NOT NULL DEFAULT 0.0,
                spend_usd REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS session_threads (
                session_id TEXT PRIMARY KEY,
                messages_json TEXT,
                updated_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_memory_events_session
            ON memory_events(session_id, id DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS semantic_cache (
                context_hash TEXT,
                question TEXT,
                embedding TEXT,
                response_json TEXT,
                created_at TIMESTAMP,
                PRIMARY KEY (context_hash, question)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_semantic_cache_ctx
            ON semantic_cache(context_hash)
            """
        ]
        await client.batch(statements)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def create_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> None:
        client = await self._ensure_conn()
        async with self.lock:
            await client.execute(
                "INSERT OR IGNORE INTO sessions (session_id, created_at, last_accessed, metadata) "
                "VALUES (?, ?, ?, ?)",
                [
                    session_id,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(metadata or {}),
                ],
            )

    async def get_session_symbols(self, session_id: str) -> list[dict[str, Any]]:
        client = await self._ensure_conn()
        res = await client.execute(
            "SELECT qualified_name, kind, score, provenance, distance "
            "FROM session_symbols WHERE session_id = ? ORDER BY symbol_id",
            [session_id],
        )
        return [row.asdict() for row in res.rows]

    async def add_session_symbol(
        self,
        session_id: str,
        symbol_id: int,
        qualified_name: str,
        kind: str,
        score: float,
        provenance: str,
        distance: int,
    ) -> None:
        client = await self._ensure_conn()
        async with self.lock:
            await client.execute(
                """
                INSERT OR IGNORE INTO session_symbols
                (session_id, symbol_id, qualified_name, kind, score, provenance, distance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    session_id,
                    symbol_id,
                    qualified_name,
                    kind,
                    score,
                    provenance,
                    distance,
                    datetime.now(timezone.utc).isoformat(),
                ],
            )

    async def get_session_schema(self, session_id: str, schema_hash: str) -> dict[str, Any] | None:
        client = await self._ensure_conn()
        res = await client.execute(
            "SELECT schema_definition, field_names FROM session_schemas "
            "WHERE session_id = ? AND schema_hash = ?",
            [session_id, schema_hash],
        )
        if res.rows:
            row = res.rows[0].asdict()
            return {
                "definition": json.loads(row["schema_definition"]),
                "fields": json.loads(row["field_names"]),
            }
        return None

    async def get_thread(self, session_id: str) -> list[dict[str, Any]]:
        client = await self._ensure_conn()
        res = await client.execute(
            "SELECT messages_json FROM session_threads WHERE session_id = ?",
            [session_id]
        )
        if res.rows:
            row = res.rows[0].asdict()
            if row["messages_json"]:
                return json.loads(row["messages_json"])
        return []

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Return thread history formatted as OpenAI Message objects."""
        history = await self.get_thread(session_id)
        messages = []
        for i, msg in enumerate(history):
            content_val = msg.get("content", "")
            if isinstance(content_val, list):
                text_parts = []
                for part in content_val:
                    if isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                    elif isinstance(part, str):
                        text_parts.append(part)
                content_val = " ".join(text_parts)
                
            messages.append({
                "id": f"msg_{session_id}_{i}",
                "object": "thread.message",
                "created_at": int(datetime.now(timezone.utc).timestamp()),
                "thread_id": session_id,
                "role": msg.get("role", "user"),
                "content": [
                    {
                        "type": "text",
                        "text": {
                            "value": str(content_val),
                            "annotations": []
                        }
                    }
                ]
            })
        return messages

    async def append_to_thread(self, session_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        client = await self._ensure_conn()
        async with self.lock:
            # Fetch existing
            res = await client.execute(
                "SELECT messages_json FROM session_threads WHERE session_id = ?",
                [session_id]
            )
            history = []
            if res.rows:
                row = res.rows[0].asdict()
                if row["messages_json"]:
                    history = json.loads(row["messages_json"])
            
            # Append new messages
            history.extend(messages)
            new_json = json.dumps(history)
            now = datetime.now(timezone.utc).isoformat()
            
            # Ensure metadata exists
            await client.execute(
                "INSERT OR IGNORE INTO sessions (session_id, created_at, last_accessed, metadata) VALUES (?, ?, ?, ?)",
                [session_id, now, now, "{}"]
            )
            
            # Upsert
            await client.execute(
                """
                INSERT INTO session_threads (session_id, messages_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    messages_json = excluded.messages_json,
                    updated_at = excluded.updated_at
                """,
                [session_id, new_json, now]
            )
            return history

    async def cache_session_schema(
        self, session_id: str, schema_hash: str, definition: dict[str, Any], field_names: list[str]
    ) -> None:
        client = await self._ensure_conn()
        async with self.lock:
            await client.execute(
                """
                INSERT OR IGNORE INTO session_schemas
                (session_id, schema_hash, schema_definition, field_names, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    session_id,
                    schema_hash,
                    json.dumps(definition),
                    json.dumps(field_names),
                    datetime.now(timezone.utc).isoformat(),
                ],
            )

    async def log_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        client = await self._ensure_conn()
        async with self.lock:
            await client.execute(
                "INSERT INTO memory_events (session_id, event_type, payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                [session_id, event_type, json.dumps(payload), datetime.now(timezone.utc).isoformat()],
            )

    async def get_session_history(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        client = await self._ensure_conn()
        res = await client.execute(
            "SELECT event_type, payload, created_at FROM memory_events "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            [session_id, limit],
        )
        return [row.asdict() for row in res.rows]

    async def cleanup_old_sessions(self, days: int = 7) -> int:
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        client = await self._ensure_conn()
        async with self.lock:
            res = await client.execute(
                "DELETE FROM sessions WHERE last_accessed < ?",
                [cutoff_date],
            )
            deleted = res.rows_affected
        return deleted

    async def session_exists(self, session_id: str) -> bool:
        client = await self._ensure_conn()
        res = await client.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", [session_id]
        )
        return len(res.rows) > 0

    async def delete_session(self, session_id: str) -> None:
        client = await self._ensure_conn()
        async with self.lock:
            await client.execute(
                "DELETE FROM sessions WHERE session_id = ?", [session_id]
            )

    async def list_all_sessions(self) -> list[dict[str, Any]]:
        client = await self._ensure_conn()
        res = await client.execute("SELECT session_id, created_at, last_accessed FROM sessions")
        return [row.asdict() for row in res.rows]

    async def add_session_fact(self, session_id: str, fact: str) -> None:
        client = await self._ensure_conn()
        async with self.lock:
            await client.execute(
                "INSERT OR IGNORE INTO session_facts (session_id, fact, created_at) VALUES (?, ?, ?)",
                [session_id, fact, datetime.now(timezone.utc).isoformat()],
            )

    async def get_session_facts(self, session_id: str) -> list[str]:
        client = await self._ensure_conn()
        res = await client.execute(
            "SELECT fact FROM session_facts WHERE session_id = ? ORDER BY id ASC",
            [session_id]
        )
        return [row.asdict()["fact"] for row in res.rows]

    # ── Semantic Cache ────────────────────────────────────────────────────────

    async def get_active_semantic_cache(self, context_hash: str, cutoff_iso: str, limit: int = 100) -> list[dict[str, Any]]:
        client = await self._ensure_conn()
        res = await client.execute(
            "SELECT question, embedding, response_json, created_at FROM semantic_cache "
            "WHERE context_hash = ? AND created_at >= ? "
            "ORDER BY created_at DESC LIMIT ?",
            [context_hash, cutoff_iso, limit]
        )
        return [row.asdict() for row in res.rows]

    async def store_semantic_cache(self, context_hash: str, question: str, embedding: list[float], response: dict[str, Any]) -> None:
        client = await self._ensure_conn()
        async with self.lock:
            await client.execute(
                """
                INSERT OR IGNORE INTO semantic_cache (context_hash, question, embedding, response_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    context_hash,
                    question,
                    json.dumps(embedding),
                    json.dumps(response),
                    datetime.now(timezone.utc).isoformat()
                ]
            )

    async def get_all_semantic_cache_entries(self, cutoff_iso: str) -> list[dict[str, Any]]:
        client = await self._ensure_conn()
        res = await client.execute(
            "SELECT context_hash, question, created_at FROM semantic_cache "
            "WHERE created_at >= ? ORDER BY created_at DESC",
            [cutoff_iso]
        )
        return [row.asdict() for row in res.rows]

    # ── Tenant Quotas ─────────────────────────────────────────────────────────

    async def get_tenant_quota(self, tenant_id: str) -> tuple[float, float]:
        client = await self._ensure_conn()
        res = await client.execute(
            "SELECT quota_usd, spend_usd FROM tenant_quotas WHERE tenant_id = ?",
            [tenant_id]
        )
        if res.rows:
            row = res.rows[0].asdict()
            return float(row["quota_usd"]), float(row["spend_usd"])
        return 0.0, 0.0

    async def set_tenant_quota(self, tenant_id: str, quota_usd: float) -> None:
        client = await self._ensure_conn()
        async with self.lock:
            now = datetime.now(timezone.utc).isoformat()
            await client.execute(
                """
                INSERT INTO tenant_quotas (tenant_id, quota_usd, spend_usd, created_at, updated_at)
                VALUES (?, ?, 0.0, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    quota_usd=excluded.quota_usd,
                    updated_at=excluded.updated_at
                """,
                [tenant_id, quota_usd, now, now]
            )

    async def increment_tenant_spend(self, tenant_id: str, cost_usd: float) -> None:
        client = await self._ensure_conn()
        async with self.lock:
            now = datetime.now(timezone.utc).isoformat()
            await client.execute(
                """
                INSERT INTO tenant_quotas (tenant_id, quota_usd, spend_usd, created_at, updated_at)
                VALUES (?, 0.0, ?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    spend_usd = spend_usd + excluded.spend_usd,
                    updated_at = excluded.updated_at
                """,
                [tenant_id, cost_usd, now, now]
            )
