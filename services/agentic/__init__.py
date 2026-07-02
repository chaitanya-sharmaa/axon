"""Agentic Optimization Package for Axon Bridge.

A collection of mathematically rigorous, semantically-transparent middleware
optimizations specifically for agentic AI workflows (ReAct, Plan-Execute,
multi-agent systems, tool-calling loops).

All optimizations:
  - Never change the semantic meaning of any message
  - Never modify user-facing prompt content
  - Only compress redundancy, normalize representation, or prune mathematically
    derivable-as-irrelevant content

Usage:
    from services.agentic import pipeline

    result = pipeline.optimize_request(
        messages=messages,
        tools=tools,
        model=req.model,
        session_id=session_id,
    )
    # result.messages, result.tools are ready to send
    # result.tokens_saved, result.savings_breakdown for metrics
"""

from services.agentic import pipeline
from services.agentic.pipeline import (
    AgenticOptimizationResult,
    optimize_request,
    update_after_response,
)
from services.agentic.session_state import agentic_state_manager

__all__ = [
    "pipeline",
    "AgenticOptimizationResult",
    "optimize_request",
    "update_after_response",
    "agentic_state_manager",
]
