"""OpenAI-compatible Assistants API endpoints for Axon Bridge.

This module provides the `/v1/threads` endpoints allowing developers to use
the standard `client.beta.threads` methods in the OpenAI SDK without custom headers.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
import time
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import litellm
from core.app_config import axon_service, memory_store
from services.pricing import estimate_savings_usd, estimate_cost_usd
from api.routes.v1_openai_routes import _compress_messages, ChatMessage

log = logging.getLogger(__name__)
router = APIRouter(tags=["openai-assistants"])


# ── Request/response models ────────────────────────────────────────────────────

class CreateMessageRequest(BaseModel):
    role: str
    content: str | list[Any]
    
class CreateRunRequest(BaseModel):
    assistant_id: str
    model: str | None = None
    instructions: str | None = None
    stream: bool | None = False
    
# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/v1/threads")
async def create_thread(authorization: str | None = Header(None)) -> JSONResponse:
    """Create a new thread."""
    if not memory_store:
        raise HTTPException(500, "Memory store is not initialized")
        
    thread_id = f"thread_{uuid.uuid4().hex}"
    await memory_store.create_session(thread_id)
    
    return JSONResponse(status_code=200, content={
        "id": thread_id,
        "object": "thread",
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "metadata": {}
    })

@router.get("/v1/threads/{thread_id}")
async def get_thread(thread_id: str, authorization: str | None = Header(None)) -> JSONResponse:
    """Retrieve a thread."""
    if not memory_store:
        raise HTTPException(500, "Memory store is not initialized")
        
    exists = await memory_store.session_exists(thread_id)
    if not exists:
        raise HTTPException(404, f"Thread {thread_id} not found")
        
    return JSONResponse(status_code=200, content={
        "id": thread_id,
        "object": "thread",
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "metadata": {}
    })

@router.post("/v1/threads/{thread_id}/messages")
async def create_message(
    thread_id: str, 
    req: CreateMessageRequest,
    authorization: str | None = Header(None)
) -> JSONResponse:
    """Create a message in a thread."""
    if not memory_store:
        raise HTTPException(500, "Memory store is not initialized")
        
    exists = await memory_store.session_exists(thread_id)
    if not exists:
        raise HTTPException(404, f"Thread {thread_id} not found")
        
    new_msg = {"role": req.role, "content": req.content}
    await memory_store.append_to_thread(thread_id, [new_msg])
    
    # Get the latest message formatted properly
    msgs = await memory_store.get_messages(thread_id)
    if not msgs:
        raise HTTPException(500, "Failed to retrieve saved message")
        
    return JSONResponse(status_code=200, content=msgs[-1])

@router.get("/v1/threads/{thread_id}/messages")
async def list_messages(thread_id: str, authorization: str | None = Header(None)) -> JSONResponse:
    """List messages in a thread."""
    if not memory_store:
        raise HTTPException(500, "Memory store is not initialized")
        
    exists = await memory_store.session_exists(thread_id)
    if not exists:
        raise HTTPException(404, f"Thread {thread_id} not found")
        
    messages = await memory_store.get_messages(thread_id)
    # The official API returns messages in descending order by default
    messages.reverse()
    
    return JSONResponse(status_code=200, content={
        "object": "list",
        "data": messages,
        "first_id": messages[0]["id"] if messages else None,
        "last_id": messages[-1]["id"] if messages else None,
        "has_more": False
    })

@router.post("/v1/threads/{thread_id}/runs")
async def create_run(
    thread_id: str,
    req: CreateRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None)
) -> JSONResponse:
    """Execute a thread run."""
    api_key = (authorization or "").removeprefix("Bearer ").strip()
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")
        
    if not memory_store:
        raise HTTPException(500, "Memory store is not initialized")
        
    exists = await memory_store.session_exists(thread_id)
    if not exists:
        raise HTTPException(404, f"Thread {thread_id} not found")

    # The actual execution logic is to:
    # 1. Fetch full history
    # 2. Add any instructions as a system message
    # 3. Compress using Token Optimizer
    # 4. Hit LLM via LiteLLM
    # 5. Append Assistant response to Thread
    # 6. Return a "Run" object (we simulate it being completed instantly since we are proxying synchronously)
    
    history_dicts = await memory_store.get_thread(thread_id)
    messages = [ChatMessage(**m) for m in history_dicts]
    
    if req.instructions:
        messages.insert(0, ChatMessage(role="system", content=req.instructions))
        
    # We fallback to gpt-4o if no model is provided
    model = req.model or os.getenv("AXON_DEFAULT_MODEL", "gpt-4o")
    
    # We pass None for session_id to disable stateful truncation, because the LLM is stateless
    # and needs the full (but flattened/compressed) payload.
    compressed_messages, metrics = _compress_messages(messages, session_id=None, model_name=model)
    
    # Call LiteLLM
    try:
        response = await litellm.acompletion(
            model=model,
            messages=compressed_messages,
            api_key=api_key,
            num_retries=2
        )
    except Exception as exc:
        raise HTTPException(502, f"Upstream API Error: {exc}") from exc
        
    resp_dict = response.model_dump()
    
    if resp_dict.get("choices") and len(resp_dict["choices"]) > 0:
        assistant_msg = resp_dict["choices"][0].get("message")
        if assistant_msg:
            await memory_store.append_to_thread(thread_id, [assistant_msg])
            
    # Return the mocked Run object representing completion
    run_id = f"run_{uuid.uuid4().hex}"
    return JSONResponse(status_code=200, content={
        "id": run_id,
        "object": "thread.run",
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "assistant_id": req.assistant_id,
        "thread_id": thread_id,
        "status": "completed",
        "model": model,
        "instructions": req.instructions,
        "usage": resp_dict.get("usage", {})
    })
