"""LLM pricing database for Axon Bridge.

Maps model identifiers to their current input/output token costs so that
``OptimizerResult`` can report actual dollar savings, not just percentages.

Prices are sourced from public API pricing pages and updated manually.
Override any entry via the ``AXON_PRICING_OVERRIDES`` environment variable::

    AXON_PRICING_OVERRIDES='{"gpt-4o": {"input": 0.003, "output": 0.012}}'

All prices are in **USD per 1,000 tokens**.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPrice:
    """Input and output cost in USD per 1,000 tokens."""
    input: float   # cost per 1k input tokens
    output: float  # cost per 1k output tokens


# ── Built-in pricing table ─────────────────────────────────────────────────────
# Source: OpenAI / Anthropic public pricing pages (June 2026)
_DEFAULT_PRICES: dict[str, ModelPrice] = {
    # OpenAI
    "gpt-4o":                   ModelPrice(input=0.005,   output=0.015),
    "gpt-4o-mini":              ModelPrice(input=0.00015, output=0.0006),
    "gpt-4-turbo":              ModelPrice(input=0.010,   output=0.030),
    "gpt-4":                    ModelPrice(input=0.030,   output=0.060),
    "gpt-3.5-turbo":            ModelPrice(input=0.0005,  output=0.0015),
    "text-embedding-3-small":   ModelPrice(input=0.00002, output=0.0),
    "text-embedding-3-large":   ModelPrice(input=0.00013, output=0.0),
    # Anthropic
    "claude-3-5-sonnet-20241022": ModelPrice(input=0.003, output=0.015),
    "claude-3-5-haiku-20241022":  ModelPrice(input=0.001, output=0.005),
    "claude-3-opus-20240229":     ModelPrice(input=0.015, output=0.075),
    "claude-3-sonnet-20240229":   ModelPrice(input=0.003, output=0.015),
    "claude-3-haiku-20240307":    ModelPrice(input=0.00025, output=0.00125),
    # Gemini
    "gemini/gemini-2.5-flash":  ModelPrice(input=0.00015, output=0.0006),
    "gemini/gemini-2.0-flash":  ModelPrice(input=0.0001,  output=0.0004),
    "gemini/gemini-1.5-pro":    ModelPrice(input=0.00125, output=0.005),
    "gemini/gemini-1.5-flash":  ModelPrice(input=0.000075, output=0.0003),
    # Shorthand aliases
    "gpt-4o-2024-05-13":        ModelPrice(input=0.005,   output=0.015),
    "cl100k_base":              ModelPrice(input=0.0005,  output=0.0015),  # GPT-3.5 proxy
}


def _load_overrides() -> dict[str, ModelPrice]:
    """Load per-model price overrides from the environment."""
    raw = os.getenv("AXON_PRICING_OVERRIDES", "")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return {k: ModelPrice(**v) for k, v in parsed.items()}
    except Exception as exc:
        log.warning("Failed to parse AXON_PRICING_OVERRIDES: %s", exc)
        return {}


# Merged table — overrides win
_PRICES: dict[str, ModelPrice] = {**_DEFAULT_PRICES, **_load_overrides()}


def get_price(model: str) -> Optional[ModelPrice]:
    """Return the ``ModelPrice`` for *model*, or ``None`` if unknown.

    Performs prefix matching so ``"gpt-4o-2024-11-20"`` matches ``"gpt-4o"``.
    """
    if model in _PRICES:
        return _PRICES[model]
    for key, price in _PRICES.items():
        if model.startswith(key):
            return price
    return None


def estimate_cost_usd(tokens: int, model: str, direction: str = "input") -> Optional[float]:
    """Estimate the cost in USD for *tokens* tokens on *model*.

    Parameters
    ----------
    tokens:
        Number of tokens.
    model:
        Model identifier (e.g. ``"gpt-4o"``).
    direction:
        ``"input"`` or ``"output"``.

    Returns
    -------
    Cost in USD, or ``None`` if the model is not in the pricing table.
    """
    price = get_price(model)
    if price is None:
        return None
    rate = price.input if direction == "input" else price.output
    return round(tokens / 1000 * rate, 8)


def estimate_savings_usd(json_tokens: int, optimized_tokens: int, model: str) -> Optional[float]:
    """Return the estimated dollar saving from using the optimized payload."""
    json_cost = estimate_cost_usd(json_tokens, model)
    opt_cost = estimate_cost_usd(optimized_tokens, model)
    if json_cost is None or opt_cost is None:
        return None
    return round(json_cost - opt_cost, 8)
