"""Agent orchestration endpoints — multi-agent dispatch with auto-cheapest encoding.

POST /agent/dispatch       — Route to the best single agent for a capability
POST /agent/swarm          — Fan-out to ALL agents (or a filtered subset)
POST /agent/parallel       — Dispatch to multiple capabilities concurrently
GET  /agent/list           — List registered agents and their capabilities
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.app_config import orchestrator, memory_store

router = APIRouter(tags=["agents"])


# ── Request models ─────────────────────────────────────────────────────────────

class DispatchRequest(BaseModel):
    payload: Any
    capability: str | None = None
    agent_name: str | None = None
    session_id: str | None = None


class ParallelDispatchRequest(BaseModel):
    payload: Any
    capabilities: list[str]
    session_id: str | None = None


class SwarmRequest(BaseModel):
    payload: Any
    filter_type: str | None = None   # e.g. "analyzer" — only dispatch that agent type
    session_id: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _agent_result_to_response(agent_result: Any) -> dict[str, Any]:
    return {
        "agent": agent_result.agent_name,
        "success": agent_result.success,
        "error": agent_result.error,
        "result": agent_result.result,
        "encoded": agent_result.encoded_output,
        "strategy_used": agent_result.strategy_used,
        "token_savings_pct": agent_result.token_savings_pct,
        "latency_ms": agent_result.latency_ms,
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/agent/list")
async def list_agents() -> dict[str, Any]:
    """List all registered agents with their capabilities."""
    return {
        "agents": orchestrator.list_agents(),
        "total": len(orchestrator.list_agents()),
    }


@router.post("/agent/dispatch")
async def dispatch(req: DispatchRequest) -> dict[str, Any]:
    """Route payload to the best matching agent.

    - If ``capability`` is given, picks the highest-priority agent that declares it.
    - If ``agent_name`` is given, routes directly to that agent.
    - The response ``encoded`` field contains the cheapest GCF/TOON/TRON encoding.
    """
    result = await orchestrator.dispatch(
        req.payload,
        capability=req.capability,
        agent_name=req.agent_name,
        session_id=req.session_id,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    if req.session_id:
        memory_store.create_session(req.session_id)
        memory_store.log_event(req.session_id, "agent_dispatch", {
            "agent": result.agent_name,
            "capability": req.capability,
            "strategy": result.strategy_used,
            "savings_pct": result.token_savings_pct,
        })

    return _agent_result_to_response(result)


@router.post("/agent/parallel")
async def parallel_dispatch(req: ParallelDispatchRequest) -> dict[str, Any]:
    """Dispatch to one agent per capability concurrently.

    All agents run in parallel; results are returned as a list.
    Use this when the same payload needs analysis by multiple specialized agents.
    """
    if not req.capabilities:
        raise HTTPException(status_code=400, detail="capabilities list must not be empty")

    parallel_result = await orchestrator.dispatch_parallel(
        req.payload,
        capabilities=req.capabilities,
        session_id=req.session_id,
    )
    return {
        "results": [_agent_result_to_response(r) for r in parallel_result.results],
        "succeeded": len(parallel_result.succeeded),
        "failed": len(parallel_result.failed),
        "total_latency_ms": parallel_result.total_latency_ms,
    }


@router.post("/agent/swarm")
async def swarm(req: SwarmRequest) -> dict[str, Any]:
    """Fan-out payload to all registered agents (Ruflo swarm_init equivalent).

    Optionally filter by ``filter_type`` (e.g. ``"analyzer"``).
    All agents run in parallel; every result is GCF-encoded with the cheapest strategy.
    """
    parallel_result = await orchestrator.swarm(
        req.payload,
        session_id=req.session_id,
        filter_type=req.filter_type,
    )
    return {
        "results": [_agent_result_to_response(r) for r in parallel_result.results],
        "succeeded": len(parallel_result.succeeded),
        "failed": len(parallel_result.failed),
        "total_latency_ms": parallel_result.total_latency_ms,
    }



