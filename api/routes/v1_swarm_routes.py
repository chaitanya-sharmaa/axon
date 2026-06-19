"""Asynchronous Swarm Routing Proxy (`/v1/swarm/completions`).

Fans out a single OpenAI-compatible request to multiple models concurrently,
and synthesizes the results into a single final answer.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

import litellm

from api.routes.v1_openai_routes import ChatMessage, _compress_messages
from core.app_config import axon_service
from services.pricing import estimate_cost_usd

router = APIRouter(tags=["swarm-proxy"])


class SwarmCompletionRequest(BaseModel):
    """Payload for swarm completions."""
    messages: list[ChatMessage]
    models: list[str] = Field(..., description="List of target models to swarm concurrently.")
    synthesizer_model: str = Field(default="gpt-4o", description="Model to synthesize the final result.")
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    user: str | None = None

    model_config = {"extra": "allow"}


@router.post("/v1/swarm/completions")
async def swarm_completions(
    req: SwarmCompletionRequest,
    raw_request: Request,
    authorization: str | None = Header(None),
    x_axon_tenant_id: str | None = Header(None),
    x_axon_session_id: str | None = Header(None),
):
    """Fan-out to multiple models and synthesize."""
    start_t = time.time()
    api_key = authorization.replace("Bearer ", "") if authorization else None
    
    # 1. Compress the prompt
    # We use the synthesizer_model to dictate compression constraints for the base prompt
    compressed_messages, metrics = _compress_messages(req.messages, x_axon_session_id, req.synthesizer_model)

    # 2. Fan-out to all models
    async def _call_model(model_name: str) -> str:
        try:
            resp = await litellm.acompletion(
                model=model_name,
                messages=compressed_messages,
                api_key=api_key,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            return f"Error from {model_name}: {str(e)}"

    swarm_responses = await asyncio.gather(*[_call_model(m) for m in req.models])

    # 3. Build Synthesizer Prompt
    synthesis_content = "You are an expert synthesizer. Combine the following AI agent perspectives into the best, most accurate final answer. Do NOT mention that you are combining them, just provide the final answer directly.\n\n"
    for idx, (m, resp) in enumerate(zip(req.models, swarm_responses)):
        synthesis_content += f"=== Agent {idx+1} ({m}) ===\n{resp}\n\n"

    synthesis_messages = [
        {"role": "system", "content": synthesis_content},
        {"role": "user", "content": "Please provide the synthesized final response now."}
    ]

    # 4. Synthesize Final Output
    extra = req.model_extra or {}
    
    if req.stream:
        async def _stream_synthesis():
            stream_resp = await litellm.acompletion(
                model=req.synthesizer_model,
                messages=synthesis_messages,
                api_key=api_key,
                stream=True,
                **extra
            )
            async for chunk in stream_resp:
                yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            _stream_synthesis(),
            media_type="text/event-stream"
        )
    else:
        # Non-streaming synthesis
        final_resp = await litellm.acompletion(
            model=req.synthesizer_model,
            messages=synthesis_messages,
            api_key=api_key,
            **extra
        )
        return JSONResponse(status_code=200, content=final_resp.model_dump())
