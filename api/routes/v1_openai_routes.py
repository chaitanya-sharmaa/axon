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
from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import asyncio
import litellm
from litellm import acompletion
from litellm.exceptions import APIError, RateLimitError, ServiceUnavailableError, Timeout

from core.app_config import axon_service, memory_store
from core.settings import settings
from services.pricing import estimate_savings_usd, estimate_cost_usd
from services.semantic_cache import semantic_cache
from services.smart_router import route_model, fallback_model
from services.fact_extractor import extract_facts_async
from services.vision_optimizer import downscale_base64_image
from services.text_pruner import prune_text

from opentelemetry import trace, metrics

# OTel setup
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Metrics
tokens_saved_counter = meter.create_counter(
    "axon.tokens.saved",
    description="Number of tokens saved by compression"
)
optimization_latency = meter.create_histogram(
    "axon.optimization.latency",
    description="Latency overhead of token optimization",
    unit="ms"
)
strategy_wins = meter.create_counter(
    "axon.strategy.wins",
    description="Number of times an encoding strategy won"
)

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

def _compress_messages(messages: list[ChatMessage], session_id: str | None, model_name: str | None = None) -> tuple[list[dict], dict]:
    """Compress each message's content and return (compressed_messages, savings_metrics)."""
    with tracer.start_as_current_span("compress_messages") as span:
        import time
        start_t = time.time()
        
        original_tokens = 0
        compressed_tokens = 0
        compressed: list[dict] = []
        
        prune_enabled = os.getenv("AXON_PRUNE_TEXT", "false").lower() == "true"

    # Find the largest message for potential prompt caching (Anthropic)
    largest_msg_idx = -1
    largest_msg_len = 0

    for idx, msg in enumerate(messages):
        d = msg.model_dump(exclude_none=True)
        content = msg.content
        
        # 1. Vision Downscaling
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    url_obj = item.get("image_url", {})
                    url_val = url_obj.get("url", "")
                    if url_val.startswith("data:image"):
                        # Extract base64, downscale, and replace
                        new_b64 = downscale_base64_image(url_val)
                        if new_b64 != url_val:
                            url_obj["url"] = new_b64
                            # Assume ~1000 tokens saved heuristically for the metrics
                            original_tokens += 1200
                            compressed_tokens += 200

        # 2. Text Pruning & Compression
        elif isinstance(content, str) and len(content) > 50:
            if len(content) > largest_msg_len:
                largest_msg_len = len(content)
                largest_msg_idx = idx

            # Prune if enabled
            if prune_enabled and len(content) > 2000:
                content = prune_text(content)

            import json
            parsed_content = content
            try:
                # Attempt to parse as JSON so structural algorithms (schema_values, TRON, etc.) can work
                parsed = json.loads(content)
                if isinstance(parsed, (dict, list)):
                    parsed_content = parsed
            except Exception:
                pass

            # Pass a message-specific session ID so the optimizer tracks state independently per message position
            msg_session_id = f"{session_id}_msg{idx}" if session_id else None
            result = axon_service._optimizer.optimize(
                {"role": msg.role, "content": parsed_content},
                session_id=msg_session_id,
            )
            original_tokens += result.json_baseline_tokens
            compressed_tokens += result.winner.token_estimate
            
            # Record strategy win
            strat_name = getattr(result.winner, "strategy", "unknown")
            strategy_wins.add(1, {"strategy": strat_name})
            
            # Only substitute if we actually saved tokens
            if result.winner.savings_vs_json_pct > 0:
                d["content"] = result.winner.encoded
            elif prune_enabled:
                d["content"] = content
                
        compressed.append(d)

    # 3. Native Provider Prompt Caching (Anthropic)
    if model_name and "claude-3" in model_name and largest_msg_idx != -1:
        # Anthropic supports 'ephemeral' caching on specific blocks
        target_msg = compressed[largest_msg_idx]
        if isinstance(target_msg["content"], str):
            target_msg["content"] = [
                {
                    "type": "text", 
                    "text": target_msg["content"], 
                    "cache_control": {"type": "ephemeral"}
                }
            ]

    savings_pct = round(
        (1 - compressed_tokens / max(1, original_tokens)) * 100, 2
    ) if original_tokens > 0 else 0.0

    saved = max(0, original_tokens - compressed_tokens)
    
    # Record Metrics
    latency_ms = (time.time() - start_t) * 1000
    optimization_latency.record(latency_ms)
    if saved > 0:
        tokens_saved_counter.add(saved)

    span.set_attribute("axon.tokens.original", original_tokens)
    span.set_attribute("axon.tokens.compressed", compressed_tokens)
    span.set_attribute("axon.tokens.saved", saved)

    return compressed, {
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "savings_pct": savings_pct,
    }


async def _stream_openai(
    url: str,
    headers: dict,
    body: dict,
    max_spend: float | None = None,
    model: str = "gpt-4o",
    tenant_id: str | None = None,
    input_cost: float = 0.0,
    api_key: str = ""
) -> AsyncIterator[str]:
    """Async generator that proxies a stream using LiteLLM with an optional budget circuit breaker."""
    accumulated_tokens = 0
    tokenizer = None
    current_model = model
    
    if max_spend is not None or (settings.enable_tenant_quotas and tenant_id):
        from services.tokenizer_factory import get_tokenizer_for_model
        tokenizer = get_tokenizer_for_model(model)
        
    # Extract required LiteLLM args
    messages = body.pop("messages", [])
    body.pop("model", None) # Prevent duplicate keyword error
    body.pop("stream", None) # Prevent duplicate keyword error
    
    try:
        response = await litellm.acompletion(
            model=current_model,
            messages=messages,
            api_key=api_key,
            stream=True,
            num_retries=2,
            **body
        )
        
        async for chunk in response:
            if max_spend is not None and tokenizer is not None:
                delta_text = chunk.choices[0].delta.content or ""
                if delta_text:
                    accumulated_tokens += len(tokenizer.encode(delta_text))
                    
                    # Calculate true output cost for the specific model
                    from services.pricing import estimate_cost_usd
                    cost = estimate_cost_usd(accumulated_tokens, current_model, direction="output")
                    if cost is None:
                        cost = (accumulated_tokens / 1000.0) * 0.015 # fallback
                    
                    if cost > max_spend:
                        log.warning(f"Circuit Breaker Triggered! Cost ${cost:.4f} exceeded budget ${max_spend}")
                        yield f'data: {{"choices": [{{"delta": {{"content": "\\n\\n[AXON BUDGET EXCEEDED - STREAM TERMINATED]"}}}}]}}\n\n'
                        yield "data: [DONE]\n\n"
                        return

            yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"
        
        yield "data: [DONE]\n\n"
        
    finally:
        if settings.enable_tenant_quotas and tenant_id and memory_store:
            output_cost = estimate_cost_usd(accumulated_tokens, current_model, direction="output") or 0.0
            total_cost = input_cost + output_cost
            if total_cost > 0:
                asyncio.create_task(memory_store.increment_tenant_spend(tenant_id, total_cost))


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
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
) -> Any:
    """OpenAI-compatible chat completions with automatic token compression.

    Supports both streaming (``stream=true``) and non-streaming responses.
    Token savings are reported in the ``x-axon-metrics`` response header.
    """
    api_key = (authorization or "").removeprefix("Bearer ").strip()
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")

    session_id = request.headers.get("X-Axon-Session-ID") or request.headers.get("X-Session-ID")
    tenant_id = request.headers.get("X-Axon-Tenant-ID")

    # Quota Enforcement
    if settings.enable_tenant_quotas and tenant_id and memory_store:
        quota, spend = await memory_store.get_tenant_quota(tenant_id)
        if quota > 0 and spend >= quota:
            raise HTTPException(429, f"Tenant quota exceeded. Spend: ${spend:.4f}, Quota: ${quota:.4f}")

    # Memory Injection
    if session_id and memory_store:
        facts = await memory_store.get_session_facts(session_id)
        if facts:
            # Inject facts into the system prompt securely
            fact_str = ",".join(facts)
            mem_msg = ChatMessage(role="system", content=f"Memory: [{fact_str}]")
            req.messages.insert(0, mem_msg)
            
    # Accumulate user messages for background extraction
    user_text = " ".join([str(m.content) for m in req.messages if m.role == "user" and isinstance(m.content, str)])

    # Compress messages
    compressed_messages, metrics = _compress_messages(req.messages, session_id, req.model)

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

    # Use the appropriate header based on key format
    if api_key.startswith("AQ."):
        # New Authorization keys must be sent via the x-goog-api-key header
        upstream_headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    else:
        # Traditional keys (or OpenAI keys) use the standard Authorization header
        upstream_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


    # Add dollar savings if model pricing is known
    savings_usd = estimate_savings_usd(
        metrics["original_tokens"], metrics["compressed_tokens"], req.model
    )

    savings_header = json.dumps(metrics)
    # Choose the correct endpoint based on the model type
    if routed_model.startswith("gemini/"):
        # Gemini models use the generateContent endpoint under /v1/models/<model>:generateContent
        model_name = routed_model.split("/")[1]
        url = f"{_OPENAI_BASE}/models/{model_name}:generateContent"
    else:
        # OpenAI-compatible models keep using the chat completions endpoint
        url = f"{_OPENAI_BASE}/chat/completions"

    if req.stream:
        max_spend_str = request.headers.get("X-Axon-Max-Spend")
        max_spend = float(max_spend_str) if max_spend_str else None
        
        headers_to_send = {"x-axon-metrics": savings_header}
        if savings_usd is not None:
            headers_to_send["x-axon-cost-saved-usd"] = str(savings_usd)
            
        input_cost = estimate_cost_usd(metrics["compressed_tokens"], routed_model, direction="input") or 0.0
            
        return StreamingResponse(
            _stream_openai(url, upstream_headers, upstream_body, max_spend, routed_model, tenant_id, input_cost, api_key),
            media_type="text/event-stream",
            headers=headers_to_send,
        )

    extra = req.model_extra or {}
    requires_json = extra.get("response_format", {}).get("type") == "json_object"
    
    async def _execute_post(current_body):
        model = current_body.pop("model")
        messages = current_body.pop("messages")
        try:
            # For Gemini models we bypass litellm and call the API directly
            if routed_model.startswith("gemini/"):
                # Build Gemini request payload
                gemini_payload = {
                    "contents": [
                        {"role": "user", "parts": [{"text": msg["content"]}]} for msg in messages
                    ]
                }
                # Send request to Gemini generateContent endpoint
                import requests
                gemini_resp = requests.post(url, json=gemini_payload, headers=upstream_headers)
                gemini_resp.raise_for_status()
                gemini_data = gemini_resp.json()
                
                # Extract text from Gemini response format
                candidates = gemini_data.get("candidates", [])
                text = ""
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text = parts[0].get("text", "")
                
                # Translate back to OpenAI standard format
                return {
                    "id": "chatcmpl-gemini",
                    "object": "chat.completion",
                    "model": routed_model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": text
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    }
                }
            else:
                # OpenAI-compatible fallback using litellm
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    api_key=api_key,
                    num_retries=2,
                    **current_body
                )
                return response.model_dump()
        finally:
            # Restore them for the healing loop or fallback if needed
            current_body["model"] = model
            current_body["messages"] = messages

    # JSON Healing Loop
    for attempt in range(3):
        try:
            resp_json = await _execute_post(upstream_body)
        except (RateLimitError, ServiceUnavailableError, Timeout) as exc:
            # Smart Fallback
            fb_model = fallback_model(routed_model)
            if fb_model != routed_model:
                upstream_body["model"] = fb_model
                try:
                    resp_json = await _execute_post(upstream_body)
                except Exception as fb_exc:
                    raise HTTPException(502, f"Fallback connection failed: {fb_exc}") from fb_exc
            else:
                raise HTTPException(502, f"Upstream error: {exc}") from exc
        except APIError as exc:
            raise HTTPException(502, f"Upstream API Error: {exc}") from exc
        except Exception as exc:
            raise HTTPException(500, f"Unexpected error: {exc}") from exc
        
        if requires_json:
            content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                try:
                    json.loads(content)
                    break # Valid JSON, exit healing loop
                except json.JSONDecodeError as e:
                    if attempt == 2:
                        break # Give up on last attempt
                    log.warning(f"JSON Healing Triggered: {e}")
                    upstream_body["messages"].append({"role": "assistant", "content": content})
                    upstream_body["messages"].append({
                        "role": "user", 
                        "content": f"Your previous output was invalid JSON. Fix this specific syntax error: {str(e)}"
                    })
                    continue # Retry LLM with the error appended
        else:
            break # Not requiring JSON, exit loop
    
    # Store successful response in Semantic Cache
    if not req.stream and emb is not None:
        semantic_cache.store_response(text_for_cache, emb, resp_json)

    # Spawn background fact extraction if we have user text
    if session_id and user_text and memory_store:
        background_tasks.add_task(extract_facts_async, session_id, user_text, api_key, memory_store)

    # Track Spend
    if settings.enable_tenant_quotas and tenant_id and memory_store:
        completion_tokens = resp_json.get("usage", {}).get("completion_tokens", 0)
        input_cost = estimate_cost_usd(metrics["compressed_tokens"], routed_model, direction="input") or 0.0
        output_cost = estimate_cost_usd(completion_tokens, routed_model, direction="output") or 0.0
        total_cost = input_cost + output_cost
        if total_cost > 0:
            background_tasks.add_task(memory_store.increment_tenant_spend, tenant_id, total_cost)

    response = JSONResponse(status_code=200, content=resp_json)
    response.headers["x-axon-metrics"] = savings_header

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

    try:
        response = await litellm.acompletion(
            model=req.model,
            messages=[], # Embeddings don't use messages in liteLLM the same way
            api_base=f"{_OPENAI_BASE}",
            api_key=api_key,
            input=req.input,
            num_retries=2
        )
    except Exception as exc:
        raise HTTPException(502, f"Upstream connection failed: {exc}") from exc

    return JSONResponse(status_code=200, content=response.model_dump())
