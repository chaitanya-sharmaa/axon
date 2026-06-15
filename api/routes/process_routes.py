"""Process endpoint: route through handlers with auto-cheapest encoding."""

from __future__ import annotations

import json
from typing import Any
from fastapi import APIRouter, HTTPException

from domain.api_models import ProcessRequest
from core.app_config import axon_service, memory_store, token_optimizer
from domain.process_handlers import get_handler, list_handlers


router = APIRouter(tags=["process"])


@router.post("/process")
async def process(req: ProcessRequest) -> dict[str, Any]:
    """Process payload through a handler.

    The response is encoded with whichever format (GCF graph, GCF session/TRON,
    GCF delta/TOON, GCF generic) produces the fewest tokens for this payload.
    The ``metrics.strategy_used`` field in the response tells you which won.
    """
    handler = get_handler(req.handler)
    if handler is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported handler: {req.handler}. Available: {list_handlers()}",
        )

    # Normalize inbound — this is the context that would be forwarded to the LLM
    normalized = axon_service.from_any_to_object(req.inbound)

    # Auto-pick cheapest encoding of the INBOUND payload (the LLM context)
    # This is what saves tokens: the bridge compresses the prompt/context before
    # it reaches the LLM, regardless of what the handler does with it.
    opt = token_optimizer.optimize(normalized, session_id=req.session_id)

    # Also run the handler so callers get the processed result alongside encoding
    result = handler(normalized)

    envelope: dict[str, Any] = {
        "encoded": opt.winner.encoded,   # cheapest encoding of the inbound context
        "metrics": opt.to_metrics(),
        "handler_result": result,        # handler-processed output
    }
    if req.session_id:
        envelope["session_id"] = req.session_id
    if axon_service.include_json_fallback:
        envelope["json"] = normalized    # original normalized inbound for reference

    # Persist to memory
    if req.session_id:
        event_payload = {
            "handler": req.handler,
            "strategy_used": opt.winner.strategy,
            "tokens_saved_pct": opt.winner.savings_vs_json_pct,
        }
        await memory_store.create_session(req.session_id)
        await memory_store.log_event(req.session_id, "process", event_payload)

    return envelope
