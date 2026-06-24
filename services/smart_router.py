import os
import logging
import itertools
from typing import Dict

log = logging.getLogger(__name__)

# Round robin iterators per provider/key-set
_key_iterators: Dict[str, itertools.cycle] = {}

def get_load_balanced_key(api_key: str) -> str:
    """If the key contains a comma, round-robin through the keys to bypass RPM limits."""
    if not api_key or "," not in api_key:
        return api_key
        
    if api_key not in _key_iterators:
        keys = [k.strip() for k in api_key.split(",") if k.strip()]
        _key_iterators[api_key] = itertools.cycle(keys)
        
    selected_key = next(_key_iterators[api_key])
    return selected_key

def analyze_complexity(text: str) -> str:
    """Returns 'high' or 'low' based on keyword heuristics and reasoning triggers."""
    if not text:
        return "low"
        
    text_lower = text.lower()
    
    # High complexity triggers (deep reasoning, code generation, complex math)
    high_complexity_keywords = [
        "think step by step", "analyze", "evaluate", "deduce", "mathematical proof",
        "system architecture", "generate code", "implement", "refactor",
        "edge case", "explain the reasoning", "json schema", "strictly adhere",
        "deep dive", "comprehensive"
    ]
    
    if any(kw in text_lower for kw in high_complexity_keywords):
        return "high"
        
    # Code formatting markers
    if "```" in text or "def " in text or "class " in text or "SELECT " in text.upper():
        return "high"
        
    # Very long context
    if len(text) > 4000:
        return "high"
        
    return "low"

def route_model(original_model: str, payload_tokens: int, prompt_text: str = "") -> str:
    """Intelligently route to Lite or Pro models within the same family based on prompt complexity."""
    if os.getenv("AXON_AUTO_ROUTING", "true").lower() != "true":
        return original_model
        
    complexity = analyze_complexity(prompt_text)
    
    # Map model families to their Lite and Pro tiers
    family_map = {
        "gpt": {"lite": "gpt-4o-mini", "pro": "gpt-4o"},
        "claude": {"lite": "claude-3-5-haiku-20241022", "pro": "claude-3-5-sonnet-20241022"},
        "gemini": {"lite": "gemini/gemini-2.5-flash", "pro": "gemini/gemini-1.5-flash"},
        "ollama": {"lite": "ollama/llama3", "pro": "ollama/llama3"}
    }
    
    family = None
    if "gpt" in original_model: family = "gpt"
    elif "claude" in original_model: family = "claude"
    elif "gemini" in original_model: family = "gemini"
    
    if family:
        if complexity == "low":
            new_model = family_map[family]["lite"]
            if original_model != new_model:
                log.info(f"Smart Router: Prompt is simple. Downgrading {original_model} -> {new_model}")
            return new_model
        elif complexity == "high":
            new_model = family_map[family]["pro"]
            if original_model != new_model:
                log.info(f"Smart Router: Prompt is complex. Upgrading {original_model} -> {new_model}")
            return new_model

    return original_model

def fallback_model(failed_model: str) -> str:
    """Provide a fallback model for 429s/503s."""
    fallbacks = {
        "gpt-4o": "gpt-4-turbo",
        "gpt-4-turbo": "gpt-4o-mini",
        "gpt-4o-mini": "gpt-3.5-turbo",
        "claude-3-5-sonnet-20240620": "claude-3-haiku-20240307",
        "claude-3-opus-20240229": "claude-3-5-sonnet-20240620",
        "gemini/gemini-2.5-flash": "gemini/gemini-2.0-flash",
        "gemini/gemini-2.0-flash": "gemini/gemini-1.5-flash",
        "gemini/gemini-1.5-pro": "gemini/gemini-1.5-flash"
    }
    fb = fallbacks.get(failed_model, failed_model)
    if fb != failed_model:
        log.info(f"Smart Router: Fallback activated. {failed_model} -> {fb}")
    return fb
