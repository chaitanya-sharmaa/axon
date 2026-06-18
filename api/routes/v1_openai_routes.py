"""OpenAI-compatible API endpoints for Axon Bridge.

Axon acts as a **drop-in proxy** for the OpenAI API.  Point any OpenAI SDK
client at Axon and get automatic token compression with zero code changes::

    import openai
    client = openai.OpenAI(
        base_url="http://localhost:8080/v1",
        api_key="any-value",       # Axon does not validate this key
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello!"}],
    )

How it works
------------
1. Receive the standard OpenAI ``/v1/chat/completions`` request.
2. Compress the ``messages`` array using the cheapest Axon strategy.
3. Forward the (compressed) request to the real OpenAI API.
4. Return the standard OpenAI response unchanged.
5. Report token savings in a custom ``x-axon-metrics`` response header.

Endpoints
---------
- ``GET  /v1/models``              — proxied model list
- ``POST /v1/chat/completions``    — compressed chat proxy (streaming + non-streaming)
- ``POST /v1/embeddings``          — compressed embeddings proxy
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import asyncio

from core.app_config import axon_service
from services.pricing import estimate_savings_usd
from services.semantic_cache import semantic_cache
from services.smart_router import route_model, fallback_model
from services.fact_extractor import extract_facts_async

log = logging.getLogger(__name__)
router = APIRouter(tags=["openai-compatible"])

_OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")


# ── Request/response models ────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str | list[Any] | None = None
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    # Pass-through: any extra fields forwarded as-is
    model_config = {"extra": "allow"}


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]
    model_config = {"extra": "allow"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compress_messages(messages: list[ChatMessage], session_id: str | None) -> tuple[list[dict], dict]:
    """Compress each message's content and return (compressed_messages, savings_metrics)."""
    original_tokens = 0
    compressed_tokens = 0
    compressed: list[dict] = []
    model = None

    for msg in messages:
        d = msg.model_dump(exclude_none=True)
        content = msg.content
        if isinstance(content, str) and len(content) > 50:
            result = axon_service._optimizer.optimize(
                {"role": msg.role, "content": content},
                session_id=session_id,
            )
            original_tokens += result.json_baseline_tokens
            compressed_tokens += result.winner.token_estimate
            # Only substitute if we actually saved tokens
            if result.winner.savings_vs_json_pct > 0:
                d["content"] = result.winner.encoded
                model = None  # model known from outer request
            compressed.append(d)
        else:
            compressed.append(d)

    savings_pct = round(
        (1 - compressed_tokens / max(1, original_tokens)) * 100, 2
    )
    return compressed, {
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "savings_pct": savings_pct,
    }


async def _stream_openai(
    url: str,
    headers: dict,
    body: dict,
) -> AsyncIterator[str]:
    """Async generator that proxies an OpenAI SSE stream."""
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", url, headers=headers, json=body) as resp:
            async for line in resp.aiter_lines():
                if line:
                    yield f"{line}\n\n"


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/v1/models")
async def list_models(authorization: str | None = Header(None)) -> JSONResponse:
    """Proxy the OpenAI model list."""
    api_key = (authorization or "").removeprefix("Bearer ").strip()
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(
                f"{_OPENAI_BASE}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Upstream connection failed: {exc}") from exc


@router.post("/v1/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    request: Request,
    authorization: str | None = Header(None),
) -> Any:
    """OpenAI-compatible chat completions with automatic token compression.

    Supports both streaming (``stream=true``) and non-streaming responses.
    Token savings are reported in the ``x-axon-metrics`` response header.
    """
    api_key = (authorization or "").removeprefix("Bearer ").strip()
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")

    session_id = request.headers.get("X-Session-ID")

    # Memory Injection
    if session_id and axon_service.memory_store:
        facts = await axon_service.memory_store.get_session_facts(session_id)
        if facts:
            # Inject facts into the system prompt securely
            fact_str = ",".join(facts)
            mem_msg = ChatMessage(role="system", content=f"Memory: [{fact_str}]")
            req.messages.insert(0, mem_msg)
            
    # Accumulate user messages for background extraction
    user_text = " ".join([str(m.content) for m in req.messages if m.role == "user" and isinstance(m.content, str)])

    # Compress messages
    compressed_messages, metrics = _compress_messages(req.messages, session_id)

    # Semantic Caching
    text_for_cache = ""
    emb = None
    if not req.stream and os.getenv("AXON_SEMANTIC_CACHE", "true").lower() == "true":
        text_for_cache = json.dumps([m.model_dump(exclude_none=True) for m in req.messages])
        cached_resp, emb = await semantic_cache.check_cache(text_for_cache, api_key)
        if cached_resp:
            # Cache hit
            metrics["savings_pct"] = 100.0  # 100% savings!
            metrics["compressed_tokens"] = 0
            savings_header = json.dumps(metrics)
            return JSONResponse(
                status_code=200, 
                content=cached_resp,
                headers={"x-axon-metrics": savings_header, "x-axon-cache": "HIT"}
            )

    # Smart Routing
    routed_model = route_model(req.model, metrics["original_tokens"])
    
    # Build the upstream payload
    upstream_body = req.model_dump(exclude_none=True)
    upstream_body["messages"] = compressed_messages
    upstream_body["model"] = routed_model

    upstream_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    savings_header = json.dumps(metrics)
    url = f"{_OPENAI_BASE}/chat/completions"

    if req.stream:
        return StreamingResponse(
            _stream_openai(url, upstream_headers, upstream_body),
            media_type="text/event-stream",
            headers={"x-axon-metrics": savings_header},
        )

    async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
        try:
            resp = await client.post(url, headers=upstream_headers, json=upstream_body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 503):
                # Smart Fallback
                fb_model = fallback_model(routed_model)
                if fb_model != routed_model:
                    upstream_body["model"] = fb_model
                    try:
                        resp = await client.post(url, headers=upstream_headers, json=upstream_body)
                        resp.raise_for_status()
                    except httpx.RequestError as fb_exc:
                        raise HTTPException(502, f"Fallback connection failed: {fb_exc}") from fb_exc
                else:
                    raise HTTPException(exc.response.status_code, f"Upstream error: {exc}") from exc
            else:
                raise HTTPException(exc.response.status_code, f"Upstream error: {exc}") from exc
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Upstream connection failed: {exc}") from exc

    resp_json = resp.json()
    
    # Store successful response in Semantic Cache
    if not req.stream and emb is not None:
        semantic_cache.store_response(text_for_cache, emb, resp_json)

    # Spawn background fact extraction if we have user text
    if session_id and user_text and axon_service.memory_store:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(extract_facts_async(session_id, user_text, api_key, axon_service.memory_store))
        except RuntimeError:
            pass

    response = JSONResponse(status_code=resp.status_code, content=resp_json)
    response.headers["x-axon-metrics"] = savings_header

    # Add dollar savings if model pricing is known
    savings_usd = estimate_savings_usd(
        metrics["original_tokens"], metrics["compressed_tokens"], req.model
    )
    if savings_usd is not None:
        response.headers["x-axon-cost-saved-usd"] = str(savings_usd)

    return response


@router.post("/v1/embeddings")
async def embeddings(
    req: EmbeddingRequest,
    authorization: str | None = Header(None),
) -> JSONResponse:
    """Proxy embeddings requests (no compression — embeddings benefit less)."""
    api_key = (authorization or "").removeprefix("Bearer ").strip()
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")

    async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
        try:
            resp = await client.post(
                f"{_OPENAI_BASE}/embeddings",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=req.model_dump(exclude_none=True),
            )
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Upstream connection failed: {exc}") from exc

    return JSONResponse(status_code=resp.status_code, content=resp.json())
