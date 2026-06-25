import os
import logging
import itertools
import hashlib
from functools import lru_cache
from typing import Dict

log = logging.getLogger(__name__)

# Round robin iterators per provider/key-set.
# FIX #8: Use a hash of the key string as the dict key so that long comma-separated
# API key lists don't leak unbounded memory. Eviction is implicit via @lru_cache.
_key_iterators: Dict[str, itertools.cycle] = {}

def get_load_balanced_key(api_key: str) -> str:
    """If the key contains a comma, round-robin through the keys to bypass RPM limits."""
    if not api_key or "," not in api_key:
        return api_key

    # FIX #8: Hash the full key string so we don't store the raw multi-key value as a dict key.
    key_hash = hashlib.md5(api_key.encode()).hexdigest()
    if key_hash not in _key_iterators:
        keys = [k.strip() for k in api_key.split(",") if k.strip()]
        _key_iterators[key_hash] = itertools.cycle(keys)

    return next(_key_iterators[key_hash])

from services.intent_classifier import classify_intent

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

from core.settings import settings

def route_model(original_model: str, payload_tokens: int, prompt_text: str = "") -> str:
    """Intelligently route to Lite or Pro models within the same family based on semantic ML intent."""
    if not settings.enable_semantic_routing:
        return original_model

    # Use our new ML-based Semantic Intent Classifier
    complexity = classify_intent(prompt_text)

    # FIX #2: Correct model tier mapping.
    # - gpt: 4o-mini (lite) vs 4o (pro)
    # - claude: haiku (lite) vs sonnet (pro)
    # - gemini: 2.5-flash is the newer/faster model (lite), 2.5-pro is the heavy reasoner (pro)
    # Ollama has no meaningful tiering — skip it entirely.
    family_map = {
        "gpt":    {"lite": "gpt-4o-mini",                    "pro": "gpt-4o"},
        "claude": {"lite": "claude-3-5-haiku-20241022",      "pro": "claude-3-5-sonnet-20241022"},
        "gemini": {"lite": "gemini/gemini-2.5-flash",         "pro": "gemini/gemini-2.5-pro"},
    }

    family = None
    if "gpt" in original_model:    family = "gpt"
    elif "claude" in original_model: family = "claude"
    elif "gemini" in original_model: family = "gemini"
    # FIX #2: Ollama removed — no lite/pro tiers exist, routing is a no-op.

    if family:
        if complexity == "low":
            new_model = family_map[family]["lite"]
            if original_model != new_model:
                log.info(f"Smart Router: Simple prompt. Downgrading {original_model} -> {new_model}")
            return new_model
        elif complexity == "high":
            new_model = family_map[family]["pro"]
            if original_model != new_model:
                log.info(f"Smart Router: Complex prompt. Upgrading {original_model} -> {new_model}")
            return new_model

    return original_model

def fallback_model(failed_model: str) -> str:
    """Provide a fallback model for 429s/503s."""
    fallbacks = {
        # OpenAI
        "gpt-4o":                        "gpt-4-turbo",
        "gpt-4-turbo":                   "gpt-4o-mini",
        "gpt-4o-mini":                   "gpt-3.5-turbo",
        # Anthropic — keep both date variants so either smart-routed or explicit model falls back correctly
        "claude-3-5-sonnet-20241022":    "claude-3-5-haiku-20241022",
        "claude-3-5-sonnet-20240620":    "claude-3-5-haiku-20241022",
        "claude-3-5-haiku-20241022":     "claude-3-haiku-20240307",
        "claude-3-opus-20240229":        "claude-3-5-sonnet-20241022",
        # Gemini
        "gemini/gemini-2.5-pro":         "gemini/gemini-2.5-flash",
        "gemini/gemini-2.5-flash":       "gemini/gemini-2.0-flash",
        "gemini/gemini-2.0-flash":       "gemini/gemini-1.5-flash-latest",
        "gemini/gemini-1.5-pro":         "gemini/gemini-1.5-flash-latest",
    }
    fb = fallbacks.get(failed_model, failed_model)
    if fb != failed_model:
        log.info(f"Smart Router: Fallback activated. {failed_model} -> {fb}")
    return fb
