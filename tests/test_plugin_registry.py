import pytest
from services.plugin_registry import register_strategy, list_strategies, encode, PluginRegistry, _REGISTRY

@pytest.fixture(autouse=True)
def cleanup_registry():
    # Save original
    original = dict(_REGISTRY)
    yield
    # Restore
    _REGISTRY.clear()
    _REGISTRY.update(original)

def test_register_strategy():
    @register_strategy("test_strat")
    def strat_fn(obj, session_id=None):
        return "test"
    
    assert "test_strat" in list_strategies()
    assert strat_fn({}, None) == "test"

def test_register_strategy_overwrite(caplog):
    @register_strategy("test_strat")
    def strat_fn1(obj, session_id=None):
        return "1"
    
    @register_strategy("test_strat")
    def strat_fn2(obj, session_id=None):
        return "2"
        
    assert "Overwriting existing plugin strategy" in caplog.text

def test_encode_success():
    PluginRegistry.register("success_strat", lambda o, s: "encoded")
    assert encode("success_strat", {}) == "encoded"
    assert PluginRegistry.encode("success_strat", {}) == "encoded"

def test_encode_unregistered():
    assert encode("nonexistent", {}) is None

def test_encode_exception():
    def exploding_strat(o, s):
        raise ValueError("boom")
    
    PluginRegistry.register("exploding", exploding_strat)
    # Should catch and return None
    assert encode("exploding", {}) is None

def test_plugin_registry_list():
    PluginRegistry.register("strat1", lambda o, s: "1")
    assert "strat1" in PluginRegistry.list_strategies()
