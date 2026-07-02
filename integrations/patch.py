import functools
import inspect
import json
import logging
from typing import Any

from core.app_config import axon_service
from services.token_optimizer import minify_scratchpad, prune_tools

logger = logging.getLogger(__name__)

def _compress_kwargs(kwargs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compresses the kwargs and returns (new_kwargs, metrics)."""
    messages = kwargs.get("messages", [])
    tools = kwargs.get("tools", [])

    original_tokens = 0
    compressed_tokens = 0

    # 1. Minify Scratchpad
    if messages:
        messages = minify_scratchpad(messages)

    # 2. Prune Tools
    if tools and messages:
        user_text = " ".join([m.get("content", "") for m in messages if isinstance(m, dict) and m.get("role") == "user"])
        if user_text:
            original_tool_count = len(tools)
            tools = prune_tools(tools, user_text, top_k=5)
            saved_tools = original_tool_count - len(tools)
            original_tokens += (original_tool_count * 150)
            compressed_tokens += (len(tools) * 150)
            kwargs["tools"] = tools

    # 3. Compress Text Content
    compressed_messages = []
    for msg in messages:
        content = msg.get("content", "")
        d = dict(msg)

        if isinstance(content, str) and len(content) > 50:
            result = axon_service._optimizer.optimize(
                {"role": d.get("role", "user"), "content": content},
                session_id=None,
            )
            original_tokens += result.json_baseline_tokens
            compressed_tokens += result.winner.token_estimate

            if result.winner.savings_vs_json_pct > 0:
                d["content"] = result.winner.encoded

        compressed_messages.append(d)

    kwargs["messages"] = compressed_messages

    savings_pct = round(
        (1 - compressed_tokens / max(1, original_tokens)) * 100, 2
    ) if original_tokens > 0 else 0.0

    metrics = {
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "savings_pct": savings_pct
    }

    return kwargs, metrics

def _sync_execute_with_healing(original_create, args, kwargs, metrics):
    requires_json = kwargs.get("response_format", {}).get("type") == "json_object"
    is_stream = kwargs.get("stream", False)

    if is_stream or not requires_json:
        response = original_create(*args, **kwargs)
        try:
            response._axon_metrics = metrics
        except AttributeError:
            pass
        return response

    for attempt in range(3):
        response = original_create(*args, **kwargs)
        try:
            response._axon_metrics = metrics
        except AttributeError:
            pass

        content = response.choices[0].message.content if hasattr(response, "choices") and response.choices else ""
        if content:
            try:
                json.loads(content)
                return response
            except json.JSONDecodeError as e:
                if attempt == 2:
                    return response
                logger.warning(f"JSON Healing Triggered: {e}")
                kwargs["messages"].append({"role": "assistant", "content": content})
                kwargs["messages"].append({"role": "user", "content": f"Your previous output was invalid JSON. Fix this specific syntax error: {str(e)}"})
    return response

async def _async_execute_with_healing(original_create, args, kwargs, metrics):
    requires_json = kwargs.get("response_format", {}).get("type") == "json_object"
    is_stream = kwargs.get("stream", False)

    if is_stream or not requires_json:
        response = await original_create(*args, **kwargs)
        try:
            response._axon_metrics = metrics
        except AttributeError:
            pass
        return response

    for attempt in range(3):
        response = await original_create(*args, **kwargs)
        try:
            response._axon_metrics = metrics
        except AttributeError:
            pass

        content = response.choices[0].message.content if hasattr(response, "choices") and response.choices else ""
        if content:
            try:
                json.loads(content)
                return response
            except json.JSONDecodeError as e:
                if attempt == 2:
                    return response
                logger.warning(f"JSON Healing Triggered: {e}")
                kwargs["messages"].append({"role": "assistant", "content": content})
                kwargs["messages"].append({"role": "user", "content": f"Your previous output was invalid JSON. Fix this specific syntax error: {str(e)}"})
    return response

def patch(client: Any) -> Any:
    """
    Patch an OpenAI client to natively intercept and compress requests 
    using Axon before sending them upstream.
    """
    if not hasattr(client, "chat") or not hasattr(client.chat, "completions"):
        logger.warning("Axon patch expected an OpenAI client. Returning unpatched.")
        return client

    original_create = client.chat.completions.create
    is_async = inspect.iscoroutinefunction(original_create)

    if is_async:
        @functools.wraps(original_create)
        async def wrapped_create(*args, **kwargs):
            new_kwargs, metrics = _compress_kwargs(kwargs)
            return await _async_execute_with_healing(original_create, args, new_kwargs, metrics)
    else:
        @functools.wraps(original_create)
        def wrapped_create(*args, **kwargs):
            new_kwargs, metrics = _compress_kwargs(kwargs)
            return _sync_execute_with_healing(original_create, args, new_kwargs, metrics)

    client.chat.completions.create = wrapped_create
    return client
