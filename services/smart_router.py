import os
import logging

log = logging.getLogger(__name__)

def route_model(original_model: str, payload_tokens: int) -> str:
    """Downgrade to a cheaper model if the payload is small and simple."""
    if os.getenv("AXON_AUTO_ROUTING", "true").lower() != "true":
        return original_model
        
    if original_model == "gpt-4o" and payload_tokens < 1000:
        log.info("Smart Router: Downgrading gpt-4o to gpt-4o-mini for small payload.")
        return "gpt-4o-mini"
        
    if "claude-3-5-sonnet" in original_model and payload_tokens < 1000:
        log.info("Smart Router: Downgrading claude-3-5-sonnet to claude-3-haiku for small payload.")
        return "claude-3-haiku-20240307"
        
    return original_model

def fallback_model(failed_model: str) -> str:
    """Provide a fallback model for 429s/503s."""
    fallbacks = {
        "gpt-4o": "gpt-4-turbo",
        "gpt-4-turbo": "gpt-4o-mini",
        "gpt-4o-mini": "gpt-3.5-turbo",
        "claude-3-5-sonnet-20240620": "claude-3-haiku-20240307",
        "claude-3-opus-20240229": "claude-3-5-sonnet-20240620"
    }
    fb = fallbacks.get(failed_model, failed_model)
    if fb != failed_model:
        log.info(f"Smart Router: Fallback activated. {failed_model} -> {fb}")
    return fb
