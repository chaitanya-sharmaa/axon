import os
from unittest.mock import patch

from services.pricing import (
    _load_overrides,
    estimate_cost_usd,
    estimate_savings_usd,
    get_price,
)


def test_get_price_exact_match():
    price = get_price("gpt-4o")
    assert price is not None
    assert price.input == 0.005

def test_get_price_prefix_match():
    price = get_price("gpt-4o-2024-11-20")
    assert price is not None
    assert price.input == 0.005

def test_get_price_unknown():
    assert get_price("unknown-model") is None

def test_estimate_cost_usd():
    # 1000 tokens of gpt-4o input = $0.005
    assert estimate_cost_usd(1000, "gpt-4o", "input") == 0.005
    # 1000 tokens of gpt-4o output = $0.015
    assert estimate_cost_usd(1000, "gpt-4o", "output") == 0.015

def test_estimate_cost_usd_unknown():
    assert estimate_cost_usd(1000, "unknown-model") is None

def test_estimate_savings_usd():
    # 1000 tokens json vs 500 optimized = 500 tokens saved
    # gpt-4o input rate = 0.005 / 1000
    # savings = 0.5 * 0.005 = 0.0025
    assert estimate_savings_usd(1000, 500, "gpt-4o") == 0.0025

def test_estimate_savings_usd_unknown():
    assert estimate_savings_usd(1000, 500, "unknown-model") is None

def test_load_overrides_empty():
    with patch.dict(os.environ, clear=True):
        assert _load_overrides() == {}

def test_load_overrides_valid():
    raw = '{"gpt-9": {"input": 0.1, "output": 0.2}}'
    with patch.dict(os.environ, {"AXON_PRICING_OVERRIDES": raw}):
        overrides = _load_overrides()
        assert "gpt-9" in overrides
        assert overrides["gpt-9"].input == 0.1

def test_load_overrides_invalid():
    with patch.dict(os.environ, {"AXON_PRICING_OVERRIDES": "invalid-json"}):
        assert _load_overrides() == {}
