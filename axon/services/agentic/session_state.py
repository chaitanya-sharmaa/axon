"""Per-session state tracking for the agentic optimization pipeline.

Each agent session gets a lightweight AgenticSessionState that persists
across turns. The state manager handles TTL-based eviction so memory
is bounded even under long-running deployments.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# ── Tool call record ──────────────────────────────────────────────────────────

@dataclass
class ToolCallRecord:
    """One completed tool call, stored for loop detection and caching."""
    tool_name: str
    args_hash: str       # sha256[:16] of (tool_name + json(args))
    result: Any          # The raw tool result content
    turn: int            # Which turn this happened on
    timestamp: float     # Unix epoch


# ── Per-session state ─────────────────────────────────────────────────────────

@dataclass
class AgenticSessionState:
    """Mutable state accumulated across turns for one agent session."""

    session_id: str
    turn: int = 0

    # ── Tool schema tracking (for differential transmission) ──────────────────
    # tool_name -> md5 of the schema dict (to detect schema changes)
    schemas_sent: dict[str, str] = field(default_factory=dict)
    # tool_name -> last turn on which this tool was actually called
    schemas_last_called: dict[str, int] = field(default_factory=dict)

    # ── Tool call history (for loop detection and result caching) ─────────────
    tool_call_history: list[ToolCallRecord] = field(default_factory=list)

    # ── Prefix caching (for provider-native KV cache injection) ───────────────
    # MD5 of the most-recently-seen system prompt block
    system_prompt_hash: str | None = None
    # Turn on which the system prompt was last sent with cache markers
    last_prefix_cache_turn: int = -1

    # ── Observation window tracking ───────────────────────────────────────────
    # Running count of tool results seen (to track window position)
    tool_result_count: int = 0

    # ── Housekeeping ──────────────────────────────────────────────────────────
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)


# ── State manager (global singleton) ─────────────────────────────────────────

class AgenticStateManager:
    """
    Thread-safe (GIL-protected) manager for per-session AgenticSessionState.

    Uses simple dict eviction:  when capacity is reached, the least-recently-
    used session is dropped.  TTL cleanup runs lazily on every 100th access.
    """

    def __init__(self, ttl_seconds: int = 3600, max_sessions: int = 500):
        self._states: dict[str, AgenticSessionState] = {}
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._access_count = 0

    def get(self, session_id: str) -> AgenticSessionState:
        """Return the state for *session_id*, creating it if needed."""
        now = time.time()
        self._access_count += 1

        # Lazy TTL cleanup every 100 accesses
        if self._access_count % 100 == 0:
            self._cleanup(now)

        if session_id in self._states:
            state = self._states[session_id]
            state.last_accessed = now
            return state

        # Evict LRU if at capacity
        if len(self._states) >= self.max_sessions:
            lru_key = min(self._states, key=lambda k: self._states[k].last_accessed)
            del self._states[lru_key]

        state = AgenticSessionState(session_id=session_id)
        self._states[session_id] = state
        return state

    def _cleanup(self, now: float) -> None:
        expired = [k for k, v in self._states.items()
                   if now - v.last_accessed > self.ttl_seconds]
        for k in expired:
            del self._states[k]

    def stats(self) -> dict[str, Any]:
        return {
            "active_sessions": len(self._states),
            "max_sessions": self.max_sessions,
            "ttl_seconds": self.ttl_seconds,
        }


# Global singleton — imported by all pipeline modules
agentic_state_manager = AgenticStateManager()
