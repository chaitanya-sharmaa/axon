import pytest
import os
from unittest.mock import patch

from services.smart_router import route_model, fallback_model, get_load_balanced_key, _key_iterators

def test_load_balanced_key_single():
    assert get_load_balanced_key("sk-123") == "sk-123"
    assert get_load_balanced_key("") == ""
    assert get_load_balanced_key(None) is None

def test_load_balanced_key_multiple():
    # Clear iterators for isolated test
    _key_iterators.clear()
    keys = "sk-1, sk-2, sk-3"
    assert get_load_balanced_key(keys) == "sk-1"
    assert get_load_balanced_key(keys) == "sk-2"
    assert get_load_balanced_key(keys) == "sk-3"
    assert get_load_balanced_key(keys) == "sk-1" # Round robin wraps around

def test_route_model_auto_routing_disabled():
    with patch.dict(os.environ, {"AXON_AUTO_ROUTING": "false"}):
        assert route_model("gpt-4o", 500) == "gpt-4o"

def test_route_model_auto_routing_enabled():
    with patch.dict(os.environ, {"AXON_AUTO_ROUTING": "true"}):
        # Downgrade triggers
        assert route_model("gpt-4o", 500) == "gpt-4o-mini"
        assert route_model("claude-3-5-sonnet", 500) == "claude-3-haiku-20240307"
        
        # Payload too large, shouldn't downgrade
        assert route_model("gpt-4o", 1500) == "gpt-4o"
        assert route_model("claude-3-5-sonnet", 1500) == "claude-3-5-sonnet"
        
        # Unsupported model shouldn't downgrade
        assert route_model("gpt-3.5-turbo", 500) == "gpt-3.5-turbo"

def test_fallback_model():
    assert fallback_model("gpt-4o") == "gpt-4-turbo"
    assert fallback_model("gpt-4-turbo") == "gpt-4o-mini"
    assert fallback_model("gpt-4o-mini") == "gpt-3.5-turbo"
    assert fallback_model("claude-3-5-sonnet-20240620") == "claude-3-haiku-20240307"
    assert fallback_model("claude-3-opus-20240229") == "claude-3-5-sonnet-20240620"
    
    # Unknown model returns itself
    assert fallback_model("unknown-model") == "unknown-model"
