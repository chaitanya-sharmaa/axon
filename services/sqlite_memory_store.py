"""Persistent session memory for GCF bridge with schema caching and symbol tracking."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


class SessionMemoryStore:
    """Persistent session memory backed by SQLite."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        created_at TIMESTAMP,
                        last_accessed TIMESTAMP,
                        metadata TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS session_symbols (
                        session_id TEXT,
                        symbol_id INTEGER,
                        qualified_name TEXT,
                        kind TEXT,
                        score REAL,
                        provenance TEXT,
                        distance INTEGER,
                        created_at TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                        PRIMARY KEY (session_id, qualified_name)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS session_schemas (
                        session_id TEXT,
                        schema_hash TEXT,
                        schema_definition TEXT,
                        field_names TEXT,
                        created_at TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                        PRIMARY KEY (session_id, schema_hash)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        event_type TEXT,
                        payload TEXT,
                        created_at TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                    )
                """)
                conn.commit()

    def create_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> None:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO sessions (session_id, created_at, last_accessed, metadata) VALUES (?, ?, ?, ?)",
                    (session_id, datetime.utcnow(), datetime.utcnow(), json.dumps(metadata or {})),
                )
                conn.commit()

    def get_session_symbols(self, session_id: str) -> list[dict[str, Any]]:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT qualified_name, kind, score, provenance, distance FROM session_symbols WHERE session_id = ? ORDER BY symbol_id",
                    (session_id,),
                ).fetchall()
                return [dict(row) for row in rows]

    def add_session_symbol(
        self,
        session_id: str,
        symbol_id: int,
        qualified_name: str,
        kind: str,
        score: float,
        provenance: str,
        distance: int,
    ) -> None:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO session_symbols 
                    (session_id, symbol_id, qualified_name, kind, score, provenance, distance, created_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (session_id, symbol_id, qualified_name, kind, score, provenance, distance, datetime.utcnow()),
                )
                conn.commit()

    def get_session_schema(self, session_id: str, schema_hash: str) -> dict[str, Any] | None:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT schema_definition, field_names FROM session_schemas WHERE session_id = ? AND schema_hash = ?",
                    (session_id, schema_hash),
                ).fetchone()
                if row:
                    return {
                        "definition": json.loads(row["schema_definition"]),
                        "fields": json.loads(row["field_names"]),
                    }
        return None

    def cache_session_schema(
        self, session_id: str, schema_hash: str, definition: dict[str, Any], field_names: list[str]
    ) -> None:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
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
                        datetime.utcnow(),
                    ),
                )
                conn.commit()

    def log_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO memory_events (session_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                    (session_id, event_type, json.dumps(payload), datetime.utcnow()),
                )
                conn.commit()

    def get_session_history(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT event_type, payload, created_at FROM memory_events WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
                return [dict(row) for row in rows]

    def cleanup_old_sessions(self, days: int = 7) -> int:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM sessions WHERE last_accessed < ?",
                    (cutoff_date,),
                )
                deleted = cursor.rowcount
                conn.execute("DELETE FROM session_symbols WHERE session_id NOT IN (SELECT session_id FROM sessions)")
                conn.execute("DELETE FROM session_schemas WHERE session_id NOT IN (SELECT session_id FROM sessions)")
                conn.execute("DELETE FROM memory_events WHERE session_id NOT IN (SELECT session_id FROM sessions)")
                conn.commit()
        return deleted

    def session_exists(self, session_id: str) -> bool:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        return row is not None

    def delete_session(self, session_id: str) -> None:
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM session_symbols WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM session_schemas WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM memory_events WHERE session_id = ?", (session_id,))
                conn.commit()
