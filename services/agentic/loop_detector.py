"""Tool Loop Detection & Circuit Breaker — Agentic Middleware Module.

Detects when an agent calls the same tool with identical arguments
repeatedly across turns (infinite loop pattern). On detection:

  1. The real tool API is NOT called.
  2. The cached result from the first call is returned directly.
  3. A synthetic notice is prepended to the cached result so the LLM
     knows it is seeing a cached value and can break the loop.

WHY THIS IS LOSSLESS:
  If (tool_name, args) is identical, the result is deterministic for
  non-mutating reads (GET-style operations), which is the vast majority
  of agentic tool calls. The notice tells the LLM the truth: this is
  a repeated call. We never modify actual API results.

SAVINGS: 100% token savings on all turns after the loop threshold.
         Plus prevents runaway API calls to external services.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from services.agentic.session_state import AgenticSessionState, ToolCallRecord

log = logging.getLogger(__name__)

# How many identical calls before we declare a loop
LOOP_THRESHOLD = 3

# Tool result cache TTL in seconds
CACHE_TTL_SECONDS = 300  # 5 minutes


# ── Hashing ───────────────────────────────────────────────────────────────────

def _call_hash(tool_name: str, arguments: Any) -> str:
    """Stable hash of (tool_name, arguments)."""
    try:
        args_str = (
            json.dumps(arguments, sort_keys=True)
            if isinstance(arguments, (dict, list))
            else str(arguments)
        )
    except Exception:
        args_str = str(arguments)
    raw = f"{tool_name}:{args_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Loop detection ────────────────────────────────────────────────────────────

def check_and_cache(
    tool_name: str,
    arguments: Any,
    state: AgenticSessionState,
) -> Tuple[bool, Optional[str]]:
    """
    Called BEFORE executing a tool call.

    Returns
    -------
    (is_loop, cached_result_or_None)
      is_loop=True  → skip the real call, use cached_result
      is_loop=False → proceed normally
    """
    now = time.time()
    h = _call_hash(tool_name, arguments)

    recent_calls = [
        r for r in state.tool_call_history
        if r.args_hash == h and now - r.timestamp < CACHE_TTL_SECONDS
    ]

    if len(recent_calls) >= LOOP_THRESHOLD - 1:
        cached = recent_calls[-1].result
        count = len(recent_calls) + 1
        log.warning(
            f"LoopDetector: '{tool_name}' called {count}× with identical args "
            f"(hash={h}). Returning cached result."
        )
        notice = (
            f"[AXON LOOP GUARD] Tool '{tool_name}' was called with identical "
            f"arguments {count} times. Returning cached result to prevent loop.\n"
        )
        result_str = (
            f"{notice}{cached}" if isinstance(cached, str)
            else f"{notice}{json.dumps(cached, default=str)[:800]}"
        )
        return True, result_str

    return False, None


def record(
    tool_name: str,
    arguments: Any,
    result: Any,
    state: AgenticSessionState,
) -> None:
    """
    Called AFTER a tool call completes successfully.
    Stores the result for future loop detection + caching.
    """
    h = _call_hash(tool_name, arguments)
    record = ToolCallRecord(
        tool_name=tool_name,
        args_hash=h,
        result=result,
        turn=state.turn,
        timestamp=time.time(),
    )
    state.tool_call_history.append(record)
    # Bounded: keep only the last 200 records per session
    if len(state.tool_call_history) > 200:
        state.tool_call_history = state.tool_call_history[-200:]


# ── Passive message-scan (for historical context pruning) ────────────────────

def find_loops_in_history(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Scan message history for duplicate tool-call / tool-result pairs and
    return info about them. Used by the dashboard / analytics, not for pruning.
    """
    seen: Dict[str, int] = {}
    loops = []
    for msg in messages:
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls", []):
                name = tc.get("function", {}).get("name", "")
                args = tc.get("function", {}).get("arguments", "")
                h = _call_hash(name, args)
                if h in seen:
                    loops.append({
                        "tool": name,
                        "first_seen_msg": seen[h],
                        "repeated": True,
                    })
                else:
                    seen[h] = id(msg)
    return loops
