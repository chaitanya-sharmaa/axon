"""OpenAI-compatible Assistants API endpoints for Axon Bridge.

This module provides the `/v1/threads` endpoints allowing developers to use
the standard `client.beta.threads` methods in the OpenAI SDK without custom headers.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import litellm
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.routes.v1_openai_routes import ChatMessage, _compress_messages
from core.app_config import memory_store
from core.settings import settings
from services.vector_store import vector_store

log = logging.getLogger(__name__)
router = APIRouter(tags=["openai-assistants"])


# ── Request/response models ────────────────────────────────────────────────────

class CreateMessageRequest(BaseModel):
    role: str
    content: str | list[Any]
    attachments: list[dict[str, Any]] | None = None

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

def _format_as_assistant_messages(history: list[dict], session_id: str) -> list[dict]:
    messages = []
    for i, msg in enumerate(history):
        content_val = msg.get("content", "")
        if isinstance(content_val, list):
            text_parts = []
            for part in content_val:
                if isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
                elif isinstance(part, str):
                    text_parts.append(part)
            content_val = " ".join(text_parts)

        messages.append({
            "id": f"msg_{session_id}_{i}",
            "object": "thread.message",
            "created_at": int(datetime.now(timezone.utc).timestamp()),
            "thread_id": session_id,
            "role": msg.get("role", "user"),
            "content": [
                {
                    "type": "text",
                    "text": {
                        "value": str(content_val),
                        "annotations": []
                    }
                }
            ]
        })
    return messages

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
    if req.attachments:
        new_msg["attachments"] = req.attachments
    await memory_store.append_to_thread(thread_id, [new_msg])

    # Get the latest message formatted properly
    raw_msgs = await memory_store.get_thread(thread_id)
    if not raw_msgs:
        raise HTTPException(500, "Failed to retrieve saved message")
    msgs = _format_as_assistant_messages(raw_msgs, thread_id)

    return JSONResponse(status_code=200, content=msgs[-1])

@router.get("/v1/threads/{thread_id}/messages")
async def list_messages(thread_id: str, authorization: str | None = Header(None)) -> JSONResponse:
    """List messages in a thread."""
    if not memory_store:
        raise HTTPException(500, "Memory store is not initialized")

    exists = await memory_store.session_exists(thread_id)
    if not exists:
        raise HTTPException(404, f"Thread {thread_id} not found")

    raw_messages = await memory_store.get_thread(thread_id)
    messages = _format_as_assistant_messages(raw_messages, thread_id)
    # The official API returns messages in descending order by default
    messages.reverse()

    return JSONResponse(status_code=200, content={
        "object": "list",
        "data": messages,
        "first_id": messages[0]["id"] if messages else None,
        "last_id": messages[-1]["id"] if messages else None,
        "has_more": False
    })

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

# ... earlier imports already present, just append the generator ...

async def _stream_assistant_run(
    thread_id: str,
    run_id: str,
    assistant_id: str,
    model: str,
    messages: list[dict],
    api_key: str,
    instructions: str | None
) -> AsyncIterator[str]:
    """Generates Server-Sent Events (SSE) matching the OpenAI Assistants API stream format."""
    # 1. thread.run.created
    run_obj = {
        "id": run_id, "object": "thread.run", "status": "queued",
        "thread_id": thread_id, "assistant_id": assistant_id, "model": model,
        "instructions": instructions, "created_at": int(time.time())
    }
    yield f"event: thread.run.created\ndata: {json.dumps(run_obj)}\n\n"

    # 2. thread.run.in_progress
    run_obj["status"] = "in_progress"
    yield f"event: thread.run.in_progress\ndata: {json.dumps(run_obj)}\n\n"

    # 3. thread.run.step.created
    step_id = f"step_{uuid.uuid4().hex}"
    step_obj = {
        "id": step_id, "object": "thread.run.step", "status": "in_progress",
        "type": "message_creation", "thread_id": thread_id, "run_id": run_id,
        "created_at": int(time.time())
    }
    yield f"event: thread.run.step.created\ndata: {json.dumps(step_obj)}\n\n"

    # 4. thread.message.created
    msg_id = f"msg_{uuid.uuid4().hex}"
    msg_obj = {
        "id": msg_id, "object": "thread.message", "status": "in_progress",
        "thread_id": thread_id, "role": "assistant", "content": [],
        "created_at": int(time.time())
    }
    yield f"event: thread.message.created\ndata: {json.dumps(msg_obj)}\n\n"
    yield f"event: thread.message.in_progress\ndata: {json.dumps(msg_obj)}\n\n"

    # 5. Call LiteLLM stream=True
    full_content = ""
    try:
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            api_key=api_key,
            stream=True,
            num_retries=2
        )
        async for chunk in response:
            if not chunk.choices:
                continue
            delta_text = chunk.choices[0].delta.content or ""
            if delta_text:
                full_content += delta_text
                # thread.message.delta
                delta_obj = {
                    "id": msg_id, "object": "thread.message.delta",
                    "delta": {"content": [{"index": 0, "type": "text", "text": {"value": delta_text}}]}
                }
                yield f"event: thread.message.delta\ndata: {json.dumps(delta_obj)}\n\n"
    except Exception as exc:
        log.error(f"Streaming error in Assistants API: {exc}")
        # Return a failed run status to the client
        run_obj["status"] = "failed"
        run_obj["last_error"] = {"code": "server_error", "message": str(exc)}
        yield f"event: thread.run.failed\ndata: {json.dumps(run_obj)}\n\n"
        return

    # 6. Save final message to DB
    if memory_store:
        await memory_store.append_to_thread(thread_id, [{"role": "assistant", "content": full_content}])

    # 7. Completed events
    msg_obj["status"] = "completed"
    msg_obj["content"] = [{"type": "text", "text": {"value": full_content}}]
    yield f"event: thread.message.completed\ndata: {json.dumps(msg_obj)}\n\n"

    step_obj["status"] = "completed"
    yield f"event: thread.run.step.completed\ndata: {json.dumps(step_obj)}\n\n"

    run_obj["status"] = "completed"
    yield f"event: thread.run.completed\ndata: {json.dumps(run_obj)}\n\n"

    yield "event: done\ndata: [DONE]\n\n"


@router.post("/v1/threads/{thread_id}/runs")
async def create_run(
    thread_id: str,
    req: CreateRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None)
):
    """Execute a thread run."""
    api_key = (authorization or "").removeprefix("Bearer ").strip()
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")

    if not memory_store:
        raise HTTPException(500, "Memory store is not initialized")

    exists = await memory_store.session_exists(thread_id)
    if not exists:
        raise HTTPException(404, f"Thread {thread_id} not found")

    history_dicts = await memory_store.get_thread(thread_id)
    messages = [ChatMessage(**m) for m in history_dicts]

    # ── Phase 4: Native RAG & File Attachments ──
    # Check if the latest user message has attachments
    if history_dicts:
        latest_msg = history_dicts[-1]
        if settings.enable_rag_context and latest_msg.get("role") == "user" and latest_msg.get("attachments"):
            file_ids = [att.get("file_id") for att in latest_msg["attachments"] if "file_id" in att]
            query_text = latest_msg.get("content", "")

            if file_ids and isinstance(query_text, str) and query_text.strip():
                log.info(f"RAG Triggered: Searching {len(file_ids)} files for query: '{query_text[:50]}...'")
                relevant_chunks = vector_store.search(file_ids, query_text, top_k=3)

                if relevant_chunks:
                    rag_context = "You are an AI assistant. Use the following retrieved document excerpts to answer the user's query.\n\n"
                    for idx, chunk in enumerate(relevant_chunks):
                        rag_context += f"--- Excerpt {idx+1} ---\n{chunk}\n\n"

                    # Inject RAG context as a system message right before the user message
                    messages.insert(-1, ChatMessage(role="system", content=rag_context))

    if req.instructions:
        messages.insert(0, ChatMessage(role="system", content=req.instructions))

    model = req.model or os.getenv("AXON_DEFAULT_MODEL", "gpt-4o")
    compressed_messages, metrics = _compress_messages(messages, session_id=None, model_name=model)

    run_id = f"run_{uuid.uuid4().hex}"

    if req.stream:
        return StreamingResponse(
            _stream_assistant_run(
                thread_id=thread_id,
                run_id=run_id,
                assistant_id=req.assistant_id,
                model=model,
                messages=compressed_messages,
                api_key=api_key,
                instructions=req.instructions
            ),
            media_type="text/event-stream"
        )

    # Non-streaming execution
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

    return JSONResponse(status_code=200, content={
        "id": run_id,
        "object": "thread.run",
        "created_at": int(time.time()),
        "assistant_id": req.assistant_id,
        "thread_id": thread_id,
        "status": "completed",
        "model": model,
        "instructions": req.instructions,
        "usage": resp_dict.get("usage", {})
    })
