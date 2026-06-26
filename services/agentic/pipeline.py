"""Agentic Optimization Pipeline — Main Orchestrator.

This is the single entry point for all agentic middleware optimizations.
Call ``optimize_request()`` before forwarding any request to the LLM.
Call ``update_after_response()`` after the LLM responds.

PIPELINE ORDER (fast → slow, stateless → stateful):
  1. error_truncator       — regex stack trace compression (stateless, ~0ms)
  2. whitespace_normalizer — Unicode + whitespace cleanup (stateless, ~0ms)
  3. scratchpad_compressor — ReAct Thought block compression (stateless, ~1ms)
  4. parallel_deduplicator — Cross-tool field deduplication (stateless, ~1ms)
  5. prefix_cacher         — Provider KV cache markers (session-aware, ~0ms)
  6. tool_schema_diff      — Schema differential filtering (session-aware, ~1ms)
  7. observation_window    — Entropy-based observation pruning (session-aware, ~2ms)

Loop detection is handled separately via ``check_loop()`` / ``record_tool_call()``.

All modules:
  - Are independently importable and testable
  - Return (modified_data, tokens_saved) for transparent metrics
  - Never change semantic content of any message
  - Degrade gracefully (if session_id is None, session-aware passes are skipped)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.agentic.session_state import AgenticSessionState, agentic_state_manager
from services.agentic import (
    error_truncator,
    whitespace_normalizer,
    scratchpad_compressor,
    parallel_deduplicator,
    prefix_cacher,
    tool_schema_diff,
    observation_window,
    loop_detector,
)

log = logging.getLogger(__name__)


# ── Result container ──────────────────────────────────────────────────────────

@dataclass
class AgenticOptimizationResult:
    """Output of ``optimize_request()``.  All fields are safe to read."""

    messages: List[Dict[str, Any]]
    tools: Optional[List[Dict[str, Any]]]

    # How many tokens the pipeline saved this turn
    tokens_saved: int = 0

    # Per-module breakdown for the dashboard / metrics
    savings_breakdown: Dict[str, int] = field(default_factory=dict)

    # Any loop detections this turn
    loop_detections: List[Dict[str, Any]] = field(default_factory=list)


# ── Main entry point ──────────────────────────────────────────────────────────

def optimize_request(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    model: str,
    session_id: Optional[str] = None,
) -> AgenticOptimizationResult:
    """
    Run all agentic optimizations on the *messages* + *tools* payload.

    Parameters
    ----------
    messages:   The full messages array from the incoming request.
    tools:      The tools/functions array, if any.
    model:      The target model name (used for provider-specific decisions).
    session_id: Per-agent-session identifier. When provided, enables the
                session-aware passes (prefix caching, schema diff, obs window).
                When None, only stateless passes run (still saves tokens).

    Returns
    -------
    AgenticOptimizationResult with optimized messages, tools, and metrics.
    """
    try:
        from core.settings import settings
        agentic_enabled = getattr(settings, "enable_agentic_optimizations", True)
    except Exception:
        agentic_enabled = True

    if not agentic_enabled:
        return AgenticOptimizationResult(messages=messages, tools=tools)

    total_saved = 0
    breakdown: Dict[str, int] = {}

    # ── Pass 1: Error truncation (stateless, always runs) ─────────────────────
    try:
        messages, saved = error_truncator.apply(messages)
        total_saved += saved
        breakdown["error_truncation"] = saved
    except Exception as e:
        log.warning(f"AgenticPipeline: error_truncator failed: {e}")

    # ── Pass 2: Whitespace normalization (stateless, always runs) ─────────────
    try:
        messages, saved = whitespace_normalizer.apply(messages)
        total_saved += saved
        breakdown["whitespace"] = saved
    except Exception as e:
        log.warning(f"AgenticPipeline: whitespace_normalizer failed: {e}")

    # ── Pass 3: Scratchpad compression (stateless, assistant msgs only) ───────
    try:
        if getattr(__import__('core.settings', fromlist=['settings']).settings,
                   'enable_agentic_scratchpad', True):
            messages, saved = scratchpad_compressor.apply(messages)
            total_saved += saved
            breakdown["scratchpad"] = saved
    except Exception as e:
        log.warning(f"AgenticPipeline: scratchpad_compressor failed: {e}")

    # ── Pass 4: Parallel tool result deduplication (stateless) ───────────────
    try:
        messages, saved = parallel_deduplicator.apply(messages)
        total_saved += saved
        breakdown["parallel_dedup"] = saved
    except Exception as e:
        log.warning(f"AgenticPipeline: parallel_deduplicator failed: {e}")

    # ── Session-aware passes (require session_id) ─────────────────────────────
    state: Optional[AgenticSessionState] = None
    if session_id:
        try:
            state = agentic_state_manager.get(session_id)
            state.turn += 1
        except Exception as e:
            log.warning(f"AgenticPipeline: state manager failed: {e}")

    if state is not None:
        # ── Pass 5: Provider prefix caching ───────────────────────────────────
        try:
            messages, tools, saved = prefix_cacher.apply(messages, tools, model, state)
            total_saved += saved
            breakdown["prefix_caching"] = saved
        except Exception as e:
            log.warning(f"AgenticPipeline: prefix_cacher failed: {e}")

        # ── Pass 6: Tool schema differential ──────────────────────────────────
        try:
            if tools and getattr(
                __import__('core.settings', fromlist=['settings']).settings,
                'enable_agentic_schema_diff', True
            ):
                tools, saved = tool_schema_diff.apply(tools, state)
                total_saved += saved
                breakdown["schema_differential"] = saved
        except Exception as e:
            log.warning(f"AgenticPipeline: tool_schema_diff failed: {e}")

        # ── Pass 7: Observation window pruning ────────────────────────────────
        try:
            if getattr(
                __import__('core.settings', fromlist=['settings']).settings,
                'enable_agentic_observation_window', True
            ):
                messages, saved = observation_window.apply(messages, state.turn)
                total_saved += saved
                breakdown["observation_window"] = saved
        except Exception as e:
            log.warning(f"AgenticPipeline: observation_window failed: {e}")

    if total_saved > 0:
        log.info(
            f"AgenticPipeline: {total_saved} tokens saved "
            f"[session={session_id or 'stateless'}, breakdown={breakdown}]"
        )

    return AgenticOptimizationResult(
        messages=messages,
        tools=tools,
        tokens_saved=total_saved,
        savings_breakdown=breakdown,
    )


# ── Post-response hook ────────────────────────────────────────────────────────

def update_after_response(
    session_id: str,
    tool_calls_made: Optional[List[str]] = None,
) -> None:
    """
    Call this AFTER the LLM response is received.

    Updates session state so that:
    - tool_schema_diff knows which schemas were actually used this turn
    """
    if not session_id:
        return
    try:
        state = agentic_state_manager.get(session_id)
        if tool_calls_made:
            tool_schema_diff.update_after_response(tool_calls_made, state)
    except Exception as e:
        log.warning(f"AgenticPipeline: update_after_response failed: {e}")


# ── Loop detection helpers (pass-through) ─────────────────────────────────────

def check_loop(
    tool_name: str,
    arguments: Any,
    session_id: str,
) -> Tuple[bool, Optional[str]]:
    """
    Check if calling *tool_name* with *arguments* would be a loop.

    Returns (is_loop, cached_result_or_None).
    """
    try:
        state = agentic_state_manager.get(session_id)
        return loop_detector.check_and_cache(tool_name, arguments, state)
    except Exception as e:
        log.warning(f"AgenticPipeline: loop check failed: {e}")
        return False, None


def record_tool_call(
    tool_name: str,
    arguments: Any,
    result: Any,
    session_id: str,
) -> None:
    """Record a completed tool call for future loop detection."""
    try:
        state = agentic_state_manager.get(session_id)
        loop_detector.record(tool_name, arguments, result, state)
    except Exception as e:
        log.warning(f"AgenticPipeline: record_tool_call failed: {e}")
