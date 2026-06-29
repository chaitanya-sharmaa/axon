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
import time
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks
from fastapi.responses import ORJSONResponse, StreamingResponse
from pydantic import BaseModel
import asyncio
import litellm
from litellm.exceptions import APIError, RateLimitError, ServiceUnavailableError, Timeout

from core.app_config import axon_service, memory_store
from core.settings import settings
from services.pricing import estimate_savings_usd, estimate_cost_usd
from services.semantic_cache import semantic_cache
from services.smart_router import route_model, fallback_model, get_load_balanced_key
from services.fact_extractor import extract_facts_async
from services.vision_optimizer import downscale_base64_image
from services.text_pruner import prune_text
from services.prompt_firewall import prompt_firewall
from services.pii_redactor import pii_redactor
from services.schema_validator import schema_validator
from services.kv_cache import kv_cache
from services.tool_compressor import compress_tools_to_prompt, reconstruct_tool_calls
from services.request_logger import request_logger
from services.agentic.pipeline import optimize_request as agentic_optimize, update_after_response as agentic_post

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
    tools: list[dict[str, Any]] | None = None
    # Pass-through: any extra fields forwarded as-is
    model_config = {"extra": "allow"}


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]
    model_config = {"extra": "allow"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compress_messages(messages: list[ChatMessage], session_id: str | None, model_name: str | None = None) -> tuple[list[dict], dict]:
    """Compress each message's content and return (compressed_messages, savings_metrics)."""
    if not settings.enable_tool_compression:
        return [m.model_dump(exclude_none=True) for m in messages], {
            "original_tokens": 0,
            "compressed_tokens": 0,
            "savings_pct": 0.0,
        }
    # FIX #5: The entire compression loop must run *inside* the span so that the
    # axon.optimization.latency histogram actually captures the true compression time.
    # Previously the span exited after 8 lines of setup, recording ~0ms every time.
    with tracer.start_as_current_span("compress_messages") as span:
        start_t = time.time()

        original_tokens = 0
        compressed_tokens = 0
        compressed: list[dict] = []

        prune_enabled = os.getenv("AXON_PRUNE_TEXT", "false").lower() == "true"
        enable_stateful = os.getenv("AXON_ENABLE_STATEFUL_COMPRESSION", "false").lower() == "true"

        # Find the largest message for potential prompt caching (Anthropic)
        largest_msg_idx = -1
        largest_msg_len = 0

        for idx, msg in enumerate(messages):
            d = msg.model_dump(exclude_none=True)
            content = msg.content

            # 1. Vision Downscaling (token-compression, ON by default)
            if isinstance(content, list) and settings.enable_vision_optimizer:
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        url_obj = item.get("image_url", {})
                        url_val = url_obj.get("url", "")
                        if url_val.startswith("data:image"):
                            new_b64 = downscale_base64_image(url_val)
                            if new_b64 != url_val:
                                url_obj["url"] = new_b64
                                original_tokens += 1200
                                compressed_tokens += 200

            # 2. Text Pruning & Compression
            elif isinstance(content, str) and len(content) > 50:
                if len(content) > largest_msg_len:
                    largest_msg_len = len(content)
                    largest_msg_idx = idx

                if prune_enabled and len(content) > 2000:
                    content = prune_text(content)

                parsed_content: Any = content
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, (dict, list)):
                        parsed_content = parsed
                except Exception:
                    pass

                msg_session_id = f"{session_id}_msg{idx}" if session_id and enable_stateful else None

                result = axon_service._optimizer.optimize(
                    {"role": msg.role, "content": parsed_content},
                    session_id=msg_session_id,
                )
                original_tokens += result.json_baseline_tokens
                compressed_tokens += result.winner.token_estimate

                strat_name = getattr(result.winner, "strategy", "unknown")
                strategy_wins.add(1, {"strategy": strat_name})

                if result.winner.savings_vs_json_pct > 0:
                    d["content"] = result.winner.encoded
                elif prune_enabled:
                    d["content"] = content

            compressed.append(d)

        # 3. Native Provider Prompt Caching — Anthropic
        if model_name and "claude-3" in model_name:
            if largest_msg_idx != -1:
                target_msg = compressed[largest_msg_idx]
                if isinstance(target_msg["content"], str):
                    target_msg["content"] = [
                        {"type": "text", "text": target_msg["content"], "cache_control": {"type": "ephemeral"}}
                    ]
            for idx, msg_dict in enumerate(compressed):
                if msg_dict["role"] == "system" and idx != largest_msg_idx and isinstance(msg_dict["content"], str) and len(msg_dict["content"]) > 100:
                    msg_dict["content"] = [
                        {"type": "text", "text": msg_dict["content"], "cache_control": {"type": "ephemeral"}}
                    ]
                    break

        # Gemini: inject cache_control hints so Gemini's server caches the KV state.
        # NOTE: Requires a PAID Gemini API plan (free tier limit=0).
        gemini_cache_enabled = os.getenv("AXON_ENABLE_GEMINI_PROMPT_CACHE", "false").lower() == "true"
        if gemini_cache_enabled and model_name and ("gemini-1.5" in model_name or "gemini-2" in model_name):
            GEMINI_CACHE_MIN_CHARS = 1000
            if largest_msg_idx != -1:
                target_msg = compressed[largest_msg_idx]
                if isinstance(target_msg["content"], str) and len(target_msg["content"]) >= GEMINI_CACHE_MIN_CHARS:
                    target_msg["content"] = [
                        {"type": "text", "text": target_msg["content"], "cache_control": {"type": "ephemeral"}}
                    ]
            for idx, msg_dict in enumerate(compressed):
                if msg_dict["role"] == "system" and idx != largest_msg_idx and isinstance(msg_dict["content"], str) and len(msg_dict["content"]) >= GEMINI_CACHE_MIN_CHARS:
                    msg_dict["content"] = [
                        {"type": "text", "text": msg_dict["content"], "cache_control": {"type": "ephemeral"}}
                    ]
                    break

        savings_pct = round(
            (1 - compressed_tokens / max(1, original_tokens)) * 100, 2
        ) if original_tokens > 0 else 0.0

        saved = max(0, original_tokens - compressed_tokens)

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
        start_t = time.time()
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
        latency_ms = (time.time() - start_t) * 1000 if 'start_t' in locals() else 0
        output_cost = 0.0
        if settings.enable_tenant_quotas and tenant_id and memory_store:
            output_cost = estimate_cost_usd(accumulated_tokens, current_model, direction="output") or 0.0
            total_cost = input_cost + output_cost
            if total_cost > 0:
                asyncio.create_task(memory_store.increment_tenant_spend(tenant_id, total_cost))
                
        request_logger.log_request(
            model=current_model,
            latency_ms=latency_ms,
            prompt_tokens=0, # Unknown in stream
            completion_tokens=accumulated_tokens,
            total_tokens=accumulated_tokens,
            cache_hit=False,
            tenant_id=tenant_id or "default",
            cost=input_cost + output_cost,
            status_code=200
        )


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/v1/models")
async def list_models(authorization: str | None = Header(None)) -> ORJSONResponse:
    """Proxy the OpenAI model list."""
    api_key = (authorization or "").removeprefix("Bearer ").strip()
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(
                f"{_OPENAI_BASE}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            return ORJSONResponse(status_code=resp.status_code, content=resp.json())
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
    start_t = time.time()
    api_key = (authorization or "").removeprefix("Bearer ").strip()
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")
        
    api_key = get_load_balanced_key(api_key)

    session_id = request.headers.get("X-Axon-Session-ID") or request.headers.get("X-Session-ID")
    tenant_id = request.headers.get("X-Axon-Tenant-ID")
    is_stateful_thread = request.headers.get("X-Axon-Stateful-Thread", "false").lower() == "true"

    # Quota Enforcement
    if settings.enable_tenant_quotas and tenant_id and memory_store:
        quota, spend = await memory_store.get_tenant_quota(tenant_id)
        if quota > 0 and spend >= quota:
            raise HTTPException(429, f"Tenant quota exceeded. Spend: ${spend:.4f}, Quota: ${quota:.4f}")

    # Memory Injection (opt-in: AXON_ENABLE_FACT_EXTRACTION)
    if settings.enable_fact_extraction and session_id and memory_store:
        facts = await memory_store.get_session_facts(session_id)
        if facts:
            fact_str = ",".join(facts)
            mem_msg = ChatMessage(role="system", content=f"Memory: [{fact_str}]")
            req.messages.insert(0, mem_msg)

    # Firewall & PII Redaction (opt-in: AXON_ENABLE_PROMPT_FIREWALL / AXON_ENABLE_PII_REDACTION)
    user_text_parts = []
    for msg in req.messages:
        if isinstance(msg.content, str):
            if msg.role == "user":
                if settings.enable_prompt_firewall and not prompt_firewall.scan(msg.content):
                    raise HTTPException(400, "Prompt Injection Detected. Request blocked.")
                user_text_parts.append(msg.content)
            if settings.enable_pii_redaction:
                msg.content = pii_redactor.redact(msg.content)

    user_text = " ".join(user_text_parts)

    # Stateful Thread Rehydration
    if session_id and is_stateful_thread and memory_store:
        new_msg_dicts = [m.model_dump(exclude_none=True) for m in req.messages]
        # Append incoming messages and fetch full history
        history = await memory_store.append_to_thread(session_id, new_msg_dicts)
        # Rehydrate request with full history
        req.messages = [ChatMessage(**m) for m in history]

    # Exact-Match KV Caching (100% token savings, $0 cost)
    kv_req_body = req.model_dump(exclude_none=True)
    if not req.stream:
        cached_exact = await kv_cache.get(kv_req_body)
        if cached_exact:
            # Inject HIT header and return immediately
            metrics_header = json.dumps({"strategy": "exact_match", "original_tokens": 0, "compressed_tokens": 0, "savings_pct": 100.0})
            
            request_logger.log_request(
                model=req.model,
                latency_ms=(time.time() - start_t) * 1000,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cache_hit=True,
                tenant_id=tenant_id or "default",
                cost=0.0,
                status_code=200
            )

            return ORJSONResponse(
                status_code=200, 
                content=cached_exact,
                headers={"x-axon-metrics": metrics_header, "x-axon-cache": "HIT"}
            )

    # ── Agentic Optimization Pipeline ─────────────────────────────────────────
    # Runs 7 passes (error truncation, whitespace, scratchpad compression,
    # parallel dedup, prefix caching, schema differential, observation window)
    # before Axon's structural compression. Stateless passes always run;
    # session-aware passes activate when session_id is present.
    agentic_result = agentic_optimize(
        messages=[m.model_dump(exclude_none=True) for m in req.messages],
        tools=req.tools,
        model=req.model,
        session_id=session_id,
    )
    # Rebuild req.messages from the optimized payload
    req.messages = [ChatMessage(**m) for m in agentic_result.messages]
    if agentic_result.tools is not None:
        req.tools = agentic_result.tools
    agentic_tokens_saved = agentic_result.tokens_saved

    # Compress messages
    # If stateful thread is enabled, pass session_id=None to disable stateful TRON/TOON 
    # delta deduplication, forcing safe structural compression (GCF).
    compress_session_id = None if is_stateful_thread else session_id
    compressed_messages, metrics = _compress_messages(req.messages, compress_session_id, req.model)

    # Tool Compression (Phase 2)
    has_tools = False
    if req.tools:
        has_tools = True
        tools_system_prompt = compress_tools_to_prompt(req.tools)
        if tools_system_prompt:
            # Inject into compressed_messages
            compressed_messages.insert(0, {"role": "system", "content": tools_system_prompt})
            
    # Semantic Caching (token-compression, ON by default: AXON_ENABLE_SEMANTIC_CACHE)
    state_dict = None
    if not req.stream and settings.enable_semantic_cache:
        msg_dicts = [m.model_dump(exclude_none=True) for m in req.messages]
        cached_resp, state_dict = await semantic_cache.check_cache(msg_dicts, api_key)
        if cached_resp:
            # Cache hit
            metrics["savings_pct"] = 100.0  # 100% savings!
            metrics["compressed_tokens"] = 0
            savings_header = json.dumps(metrics)
            
            resp_dict = cached_resp
            
            # Reconstruct tool_calls from simulated XML format
            if has_tools and resp_dict.get("choices") and len(resp_dict["choices"]) > 0:
                assistant_msg = resp_dict["choices"][0].get("message", {})
                content_str = assistant_msg.get("content") or ""
                reconstructed = reconstruct_tool_calls(content_str)
                
                if reconstructed:
                    # Override the text content with the tool_calls object
                    # to maintain 100% OpenAI SDK compatibility
                    assistant_msg["content"] = None
                    assistant_msg["tool_calls"] = reconstructed
                    resp_dict["choices"][0]["finish_reason"] = "tool_calls"
                    
            request_logger.log_request(
                model=req.model,
                latency_ms=(time.time() - start_t) * 1000,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cache_hit=True,
                tenant_id=tenant_id or "default",
                cost=0.0,
                status_code=200
            )

            return ORJSONResponse(
                status_code=200, 
                content=resp_dict,
                headers={"x-axon-metrics": savings_header, "x-axon-cache": "HIT"}
            )

    # Smart Routing (Prompt Complexity aware)
    routed_model = route_model(req.model, metrics["original_tokens"], user_text)
    
    # Build the upstream payload
    upstream_body = req.model_dump(exclude_none=True)
    upstream_body["messages"] = compressed_messages
    upstream_body["model"] = routed_model
    if has_tools and "tools" in upstream_body:
        # Drop the verbose tools array from the payload sent to LiteLLM,
        # saving massive amounts of tokens because we already injected the
        # compressed python signature into the system prompt!
        del upstream_body["tools"]

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

    # Merge agentic savings into the metrics header
    metrics["agentic_tokens_saved"] = agentic_tokens_saved
    metrics["agentic_breakdown"] = agentic_result.savings_breakdown

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
    req_type = extra.get("response_format", {}).get("type")
    requires_json = req_type in ("json_object", "json_schema")
    json_schema = extra.get("response_format", {}).get("json_schema", {}).get("schema")
    
    # Inject logprobs to power Shannon Entropy Hallucination Guard.
    # logprobs is a native OpenAI API feature. It is reliably supported by models
    # served via the OpenAI API or locally via Ollama (which mirrors the OpenAI spec).
    # Gemini and Anthropic either reject it or return incompatible formats, so we
    # gate it to known-good providers.
    _LOGPROB_PROVIDERS = ("gpt", "openai/")
    _logprobs_enabled = (
        not req.stream
        and any(routed_model.startswith(p) for p in _LOGPROB_PROVIDERS)
        and "gemini" not in routed_model
    )
    if _logprobs_enabled:
        upstream_body["logprobs"] = True
        upstream_body["top_logprobs"] = 5
        log.debug(f"Shannon Entropy Guard enabled for model: {routed_model}")

    async def _execute_post(current_body):
        import math
        model = current_body.pop("model")
        messages = current_body.pop("messages")
        # BUG FIX: Capture the logprobs intent *before* popping from the body,
        # so the entropy check below is not fooled by a mutated dict.
        # BUG FIX: Only use drop_params for providers that don't support logprobs.
        # For logprob-capable providers, we must NOT drop the param or LiteLLM
        # will silently strip it and the entropy guard will never fire.
        _request_logprobs = current_body.get("logprobs", False)
        _should_drop = not _request_logprobs
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=api_key,
                num_retries=2,
                drop_params=_should_drop,
                **current_body
            )
            resp_dict = response.model_dump()

            # Shannon Entropy Calculation
            # BUG FIX: Use dedicated _request_logprobs boolean captured before the
            # dict was mutated, not "logprobs" in current_body (which may be gone).
            if _request_logprobs and resp_dict.get("choices") and resp_dict["choices"][0].get("logprobs"):
                content_logprobs = resp_dict["choices"][0]["logprobs"].get("content", [])
                if content_logprobs:
                    total_entropy = 0.0
                    for token_data in content_logprobs:
                        top_lps = token_data.get("top_logprobs", [])
                        token_entropy = 0.0
                        for lp_info in top_lps:
                            lp = lp_info.get("logprob", 0.0)
                            p = math.exp(lp)
                            if p > 0:
                                token_entropy -= p * math.log2(p)
                        total_entropy += token_entropy

                    avg_entropy = total_entropy / len(content_logprobs)
                    resp_dict["_axon_shannon_entropy"] = avg_entropy
                    log.debug(f"Shannon Entropy: {avg_entropy:.4f}")

                    # Configurable threshold via env var (default 1.5)
                    entropy_threshold = float(os.getenv("AXON_ENTROPY_THRESHOLD", "1.5"))
                    if avg_entropy > entropy_threshold:
                        raise ValueError(
                            f"Hallucination detected (Shannon Entropy {avg_entropy:.2f} > {entropy_threshold})"
                        )

            # Save the assistant's reply to the stateful thread
            if session_id and is_stateful_thread and memory_store:
                if resp_dict.get("choices") and len(resp_dict["choices"]) > 0:
                    assistant_msg = resp_dict["choices"][0].get("message")
                    if assistant_msg:
                        await memory_store.append_to_thread(session_id, [assistant_msg])

            return resp_dict
        finally:
            # Restore them for the healing loop or fallback if needed
            current_body["model"] = model
            current_body["messages"] = messages

    # JSON Healing Loop
    resp_json = None
    last_val_exc = None
    for attempt in range(3):
        try:
            resp_json = await _execute_post(upstream_body)
        except ValueError as val_exc:
            # Hallucination detected via Shannon Entropy!
            log.warning(f"Attempt {attempt+1}: {val_exc}. Falling back to uncompressed raw JSON payload to heal.")
            upstream_body["messages"] = req.model_dump()["messages"]
            last_val_exc = val_exc
            continue
        except (RateLimitError, ServiceUnavailableError, Timeout) as exc:
            # Smart Fallback Cascading
            current_fb_model = routed_model
            success = False
            last_exc = exc
            
            while True:
                next_fb_model = fallback_model(current_fb_model)
                if next_fb_model == current_fb_model:
                    break
                    
                current_fb_model = next_fb_model
                upstream_body["model"] = current_fb_model
                try:
                    resp_json = await _execute_post(upstream_body)
                    success = True
                    break
                except (RateLimitError, ServiceUnavailableError, Timeout) as fb_exc:
                    last_exc = fb_exc
                    log.warning(f"Fallback model {current_fb_model} failed with RateLimit/Timeout. Trying next...")
                    continue
                except Exception as fb_exc:
                    raise HTTPException(502, f"Fallback connection failed on {current_fb_model}: {fb_exc}") from fb_exc
                    
            if not success:
                raise HTTPException(502, f"All fallback models failed. Last error: {last_exc}") from last_exc
        except APIError as exc:
            raise HTTPException(502, f"Upstream API Error: {exc}") from exc
        except Exception as exc:
            raise HTTPException(500, f"Unexpected error: {exc}") from exc
        
        if requires_json:
            if not resp_json:
                resp_dict: dict[str, Any] = {}
            else:
                resp_dict = resp_json if isinstance(resp_json, dict) else (resp_json.model_dump() if hasattr(resp_json, "model_dump") else {})
            content = resp_dict.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                try:
                    json.loads(content)
                    
                    if json_schema:
                        is_valid, err_msg, _ = schema_validator.validate_output(content, json_schema)
                        if not is_valid:
                            raise ValueError(err_msg)
                            
                    break # Valid JSON and Schema, exit healing loop
                except json.JSONDecodeError as e:
                    err_msg = f"Your previous output was invalid JSON. Fix this syntax error: {str(e)}"
                except ValueError as e:
                    err_msg = str(e)
                    
                if attempt == 2:
                    break # Give up on last attempt
                log.warning(f"JSON Healing Triggered: {err_msg}")
                upstream_body["messages"].append({"role": "assistant", "content": content})
                upstream_body["messages"].append({
                    "role": "user", 
                    "content": err_msg
                })
                continue # Retry LLM with the error appended
        else:
            break # Not requiring JSON, exit loop
    
    if resp_json is None:
        if last_val_exc:
            raise HTTPException(502, f"Failed to heal hallucination: {last_val_exc}") from last_val_exc
        raise HTTPException(502, "Failed to get a valid response from the model.")

    # Store successful response in Semantic Cache
    if not req.stream and settings.enable_semantic_cache and state_dict is not None:
        await semantic_cache.store_response(state_dict, resp_json)

    # Spawn background fact extraction (opt-in: AXON_ENABLE_FACT_EXTRACTION)
    if settings.enable_fact_extraction and session_id and user_text and memory_store:
        background_tasks.add_task(extract_facts_async, session_id, user_text, api_key, memory_store)

    # Update agentic session state with which tools the LLM called this turn
    if session_id and resp_json:
        tool_calls_made = []
        for choice in resp_json.get("choices", []):
            for tc in choice.get("message", {}).get("tool_calls") or []:
                name = tc.get("function", {}).get("name")
                if name:
                    tool_calls_made.append(name)
        if tool_calls_made:
            background_tasks.add_task(agentic_post, session_id, tool_calls_made)

    # Reconstruct tool_calls from simulated XML format
    if has_tools and resp_json.get("choices") and len(resp_json["choices"]) > 0:
        assistant_msg = resp_json["choices"][0].get("message", {})
        content_str = assistant_msg.get("content") or ""
        reconstructed = reconstruct_tool_calls(content_str)
        
        if reconstructed:
            # Override the text content with the tool_calls object
            # to maintain 100% OpenAI SDK compatibility
            assistant_msg["content"] = None
            assistant_msg["tool_calls"] = reconstructed
            resp_json["choices"][0]["finish_reason"] = "tool_calls"

    response = ORJSONResponse(status_code=200, content=resp_json)
    response.headers["x-axon-metrics"] = savings_header

    if savings_usd is not None:
        response.headers["x-axon-cost-saved-usd"] = str(savings_usd)

    # Cache successful non-streaming responses
    if not req.stream and response.status_code == 200:
        await kv_cache.set(kv_req_body, resp_json)

    # ── Logging & Spend Tracking ─────────────────────────────────────────────
    latency_ms = (time.time() - start_t) * 1000
    usage = resp_json.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", metrics.get("original_tokens", 0))
    completion_tokens = usage.get("completion_tokens", 0)
    input_cost = estimate_cost_usd(metrics["compressed_tokens"], routed_model, direction="input") or 0.0
    output_cost = estimate_cost_usd(completion_tokens, routed_model, direction="output") or 0.0
    total_cost = input_cost + output_cost

    # Track tenant spend
    if settings.enable_tenant_quotas and tenant_id and memory_store and total_cost > 0:
        background_tasks.add_task(memory_store.increment_tenant_spend, tenant_id, total_cost)

    request_logger.log_request(
        model=routed_model,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        cache_hit=False,
        tenant_id=tenant_id or "default",
        cost=total_cost,
        status_code=response.status_code
    )

    return response


@router.post("/v1/embeddings")
async def embeddings(
    req: EmbeddingRequest,
    authorization: str | None = Header(None),
) -> ORJSONResponse:
    """Proxy embeddings requests (no compression — embeddings benefit less)."""
    api_key = (authorization or "").removeprefix("Bearer ").strip()
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")

    try:
        # BUG FIX: Use litellm.aembedding for the /embeddings endpoint, not acompletion
        response = await litellm.aembedding(
            model=req.model,
            api_base=f"{_OPENAI_BASE}",
            api_key=api_key,
            input=req.input,
            num_retries=2
        )
    except Exception as exc:
        raise HTTPException(502, f"Upstream connection failed: {exc}") from exc

    return ORJSONResponse(status_code=200, content=response.model_dump())
