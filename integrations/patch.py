import functools
import json
import logging
from typing import Any, Dict

from pydantic import BaseModel

from core.app_config import axon_service
from services.token_optimizer import minify_scratchpad, prune_tools

logger = logging.getLogger(__name__)

class AxonMetricsResponse:
    """Wrapper that injects metrics onto the original OpenAI response."""
    def __init__(self, response, metrics):
        self._response = response
        self._axon_metrics = metrics
        
    def __getattr__(self, name):
        return getattr(self._response, name)
        
    def __repr__(self):
        return repr(self._response)

def patch(client: Any) -> Any:
    """
    Patch an OpenAI client to natively intercept and compress requests 
    using Axon before sending them upstream.
    
    Usage:
        import openai
        from bridge.integrations.patch import patch
        
        client = patch(openai.OpenAI())
        response = client.chat.completions.create(...)
        print(response._axon_metrics)
    """
    
    if not hasattr(client, "chat") or not hasattr(client.chat, "completions"):
        logger.warning("Axon patch expected an OpenAI client. Returning unpatched.")
        return client

    original_create = client.chat.completions.create

    @functools.wraps(original_create)
    def wrapped_create(*args, **kwargs):
        messages = kwargs.get("messages", [])
        tools = kwargs.get("tools", [])
        model = kwargs.get("model", "gpt-4o")
        
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
                # Roughly estimate tool token savings
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
        
        # Execute original API call
        response = original_create(*args, **kwargs)
        
        # Inject metrics
        savings_pct = round(
            (1 - compressed_tokens / max(1, original_tokens)) * 100, 2
        ) if original_tokens > 0 else 0.0
        
        metrics = {
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "savings_pct": savings_pct
        }
        
        return AxonMetricsResponse(response, metrics)

    client.chat.completions.create = wrapped_create
    return client
