"""Persistent session memory for Axon bridge with schema caching and symbol tracking."""

from __future__ import annotations

import asyncio
import json
import logging
import aiosqlite
from datetime import datetime, timedelta, timezone
from typing import Any
from services.memory_store import BaseMemoryStore

log = logging.getLogger(__name__)


class SessionMemoryStore(BaseMemoryStore):
    """Persistent session memory backed by SQLite.

    Key improvements over the naive per-call connection pattern:

    * **Single persistent connection** — eliminates the open/close overhead
      on every database operation.
    * **WAL journal mode** — readers never block writers; writers never block
      readers.  Concurrent ``GET /memory/session/...`` calls therefore no
      longer queue behind each other.
    * **ON DELETE CASCADE** — deleting a session row automatically removes all
      child rows (symbols, schemas, events), so ``delete_session`` and
      ``cleanup_old_sessions`` only need to touch one table.
    * **Reads are lock-free** — only write operations acquire ``self.lock``.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self.lock = asyncio.Lock()
        self._conn: aiosqlite.Connection | None = None
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._ensure_conn())
        except RuntimeError:
            asyncio.run(self._ensure_conn())

    # ── Connection management ──────────────────────────────────────────────────

    async def _ensure_conn(self) -> aiosqlite.Connection:
        """Return (or lazily create) the shared persistent connection."""
        if self._conn is None:
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            # WAL: readers don't block writers and vice-versa.
            await conn.execute("PRAGMA journal_mode=WAL")
            # Enforce FK constraints so ON DELETE CASCADE works correctly.
            await conn.execute("PRAGMA foreign_keys=ON")
            await self._init_schema(conn)
            self._conn = conn
        return self._conn

    async def close(self) -> None:
        """Close the persistent connection (call this on app shutdown)."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            log.debug("SQLite connection closed.")

    # ── Schema initialisation ──────────────────────────────────────────────────

    async def _init_schema(self, conn: aiosqlite.Connection) -> None:
        """Create tables if they don't already exist."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TIMESTAMP,
                last_accessed TIMESTAMP,
                metadata TEXT
            )
        """)
        await conn.execute("""
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
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS session_schemas (
                session_id TEXT,
                schema_hash TEXT,
                schema_definition TEXT,
                field_names TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
                PRIMARY KEY (session_id, schema_hash)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                event_type TEXT,
                payload TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS session_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                fact TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
                UNIQUE (session_id, fact)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tenant_quotas (
                tenant_id TEXT PRIMARY KEY,
                quota_usd REAL NOT NULL DEFAULT 0.0,
                spend_usd REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        await conn.commit()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def create_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> None:
        conn = await self._ensure_conn()
        async with self.lock:
            await conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, created_at, last_accessed, metadata) "
                "VALUES (?, ?, ?, ?)",
                (
                    session_id,
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                    json.dumps(metadata or {}),
                ),
            )
            await conn.commit()

    async def get_session_symbols(self, session_id: str) -> list[dict[str, Any]]:
        """Read-only — no lock required with WAL mode."""
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT qualified_name, kind, score, provenance, distance "
            "FROM session_symbols WHERE session_id = ? ORDER BY symbol_id",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

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
        conn = await self._ensure_conn()
        async with self.lock:
            await conn.execute(
                """
                INSERT OR IGNORE INTO session_symbols
                (session_id, symbol_id, qualified_name, kind, score, provenance, distance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    symbol_id,
                    qualified_name,
                    kind,
                    score,
                    provenance,
                    distance,
                    datetime.now(timezone.utc),
                ),
            )
            await conn.commit()

    async def get_session_schema(self, session_id: str, schema_hash: str) -> dict[str, Any] | None:
        """Read-only — no lock required with WAL mode."""
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT schema_definition, field_names FROM session_schemas "
            "WHERE session_id = ? AND schema_hash = ?",
            (session_id, schema_hash),
        )
        row = await cursor.fetchone()
        if row:
            return {
                "definition": json.loads(row["schema_definition"]),
                "fields": json.loads(row["field_names"]),
            }
        return None

    async def cache_session_schema(
        self, session_id: str, schema_hash: str, definition: dict[str, Any], field_names: list[str]
    ) -> None:
        conn = await self._ensure_conn()
        async with self.lock:
            await conn.execute(
                """
                INSERT OR IGNORE INTO session_schemas
                (session_id, schema_hash, schema_definition, field_names, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    schema_hash,
                    json.dumps(definition),
                    json.dumps(field_names),
                    datetime.now(timezone.utc),
                ),
            )
            await conn.commit()

    async def log_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        conn = await self._ensure_conn()
        async with self.lock:
            await conn.execute(
                "INSERT INTO memory_events (session_id, event_type, payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, event_type, json.dumps(payload), datetime.now(timezone.utc)),
            )
            await conn.commit()

    async def get_session_history(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Read-only — no lock required with WAL mode."""
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT event_type, payload, created_at FROM memory_events "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def cleanup_old_sessions(self, days: int = 7) -> int:
        """Delete sessions older than *days* days.

        With ``ON DELETE CASCADE``, child rows (symbols, schemas, events)
        are removed automatically — no manual cleanup of child tables needed.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        conn = await self._ensure_conn()
        async with self.lock:
            cursor = await conn.execute(
                "DELETE FROM sessions WHERE last_accessed < ?",
                (cutoff_date,),
            )
            deleted = cursor.rowcount
            await conn.commit()
        return deleted

    async def session_exists(self, session_id: str) -> bool:
        """Read-only — no lock required with WAL mode."""
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return row is not None

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and all its child rows (via ON DELETE CASCADE)."""
        conn = await self._ensure_conn()
        async with self.lock:
            await conn.execute(
                "DELETE FROM sessions WHERE session_id = ?", (session_id,)
            )
            await conn.commit()

    async def list_all_sessions(self) -> list[dict[str, Any]]:
        conn = await self._ensure_conn()
        cursor = await conn.execute("SELECT session_id, created_at, last_accessed FROM sessions")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def add_session_fact(self, session_id: str, fact: str) -> None:
        conn = await self._ensure_conn()
        async with self.lock:
            await conn.execute(
                "INSERT OR IGNORE INTO session_facts (session_id, fact, created_at) VALUES (?, ?, ?)",
                (session_id, fact, datetime.now(timezone.utc)),
            )
            await conn.commit()

    async def get_session_facts(self, session_id: str) -> list[str]:
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT fact FROM session_facts WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        )
        rows = await cursor.fetchall()
        return [row["fact"] for row in rows]

    # ── Tenant Quotas ─────────────────────────────────────────────────────────

    async def get_tenant_quota(self, tenant_id: str) -> tuple[float, float]:
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT quota_usd, spend_usd FROM tenant_quotas WHERE tenant_id = ?",
            (tenant_id,)
        )
        row = await cursor.fetchone()
        if row:
            return float(row["quota_usd"]), float(row["spend_usd"])
        return 0.0, 0.0

    async def set_tenant_quota(self, tenant_id: str, quota_usd: float) -> None:
        conn = await self._ensure_conn()
        async with self.lock:
            now = datetime.now(timezone.utc)
            await conn.execute(
                """
                INSERT INTO tenant_quotas (tenant_id, quota_usd, spend_usd, created_at, updated_at)
                VALUES (?, ?, 0.0, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    quota_usd=excluded.quota_usd,
                    updated_at=excluded.updated_at
                """,
                (tenant_id, quota_usd, now, now)
            )
            await conn.commit()

    async def increment_tenant_spend(self, tenant_id: str, cost_usd: float) -> None:
        conn = await self._ensure_conn()
        async with self.lock:
            now = datetime.now(timezone.utc)
            await conn.execute(
                """
                UPDATE tenant_quotas
                SET spend_usd = spend_usd + ?, updated_at = ?
                WHERE tenant_id = ?
                """,
                (cost_usd, now, tenant_id)
            )
            await conn.commit()
