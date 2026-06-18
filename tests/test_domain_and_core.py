import os
import json
import logging
from unittest.mock import patch

from domain.process_handlers import (
    handler_echo,
    handler_active_items,
    handler_graph_processor,
    get_handler,
    list_handlers
)
from core.settings import _as_bool, _as_float, _as_list, load_settings
from core.logging_config import configure_logging, request_id_var, _JSONFormatter

# --- Domain Process Handlers Tests ---

def test_handler_echo():
    assert handler_echo("test") == {"echo": "test"}

def test_handler_active_items():
    # Invalid payload
    assert handler_active_items("not_a_dict")["summary"]["total"] == 0
    assert handler_active_items({"items": "not_a_list"})["summary"]["total"] == 0
    
    # Valid payload
    payload = {
        "items": [
            {"id": 1, "status": "active"},
            {"id": 2, "status": "inactive"},
            "not_a_dict",
            {"id": 3, "status": "active"}
        ]
    }
    res = handler_active_items(payload)
    assert res["summary"]["total"] == 4
    assert res["summary"]["active"] == 2
    assert len(res["active_items"]) == 2

def test_handler_graph_processor():
    # Invalid
    assert handler_graph_processor("string")["symbols_processed"] == 0
    
    # Empty
    res = handler_graph_processor({})
    assert res["symbols_processed"] == 0
    assert res["edges_processed"] == 0
    
    # Valid
    payload = {
        "symbols": [
            {"type": "function", "module": "a"},
            {"type": "class", "module": "b"},
            {"module": "a"} # missing type defaults to unknown
        ],
        "edges": [
            {"type": "calls"},
            {"type": "inherits"}
        ]
    }
    res = handler_graph_processor(payload)
    assert res["symbols_processed"] == 3
    assert res["edges_processed"] == 2
    assert res["symbols_by_type"]["function"] == 1
    assert res["symbols_by_type"]["unknown"] == 1
    assert res["symbols_by_module"]["a"] == 2
    assert res["edge_types"]["calls"] == 1

def test_handler_registry():
    assert "echo" in list_handlers()
    assert get_handler("echo") == handler_echo
    assert get_handler("missing") is None


# --- Core Settings Tests ---

def test_settings_as_bool():
    assert _as_bool(None, True) is True
    assert _as_bool("1", False) is True
    assert _as_bool("true", False) is True
    assert _as_bool("yes", False) is True
    assert _as_bool("on", False) is True
    assert _as_bool("false", True) is False
    assert _as_bool("0", True) is False

def test_settings_as_float():
    assert _as_float(None, 1.5) == 1.5
    assert _as_float("2.5", 1.5) == 2.5
    assert _as_float("invalid", 1.5) == 1.5

def test_settings_as_list():
    assert _as_list(None, ["a", "b"]) == ["a", "b"]
    assert _as_list("x, y, z", ["a"]) == ["x", "y", "z"]
    assert _as_list("   ", ["a"]) == ["a"]

def test_load_settings():
    env = {
        "AXON_PORT": "9090",
        "AXON_APP_TITLE": "Test App",
        "AXON_INCLUDE_JSON_FALLBACK": "false",
        "AXON_ALLOWED_DOMAINS": "a.com, b.com",
    }
    with patch.dict(os.environ, env):
        s = load_settings()
        assert s.port == 9090
        assert s.app_title == "Test App"
        assert s.include_json_fallback is False
        assert s.allowed_domains == ["a.com", "b.com"]

def test_load_settings_invalid_port():
    with patch.dict(os.environ, {"AXON_PORT": "invalid"}):
        s = load_settings()
        assert s.port == 8080


# --- Core Logging Tests ---

def test_configure_logging_text():
    configure_logging(log_format="text", log_level="DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    # Should have the formatter we set
    assert len(root.handlers) > 0
    assert not isinstance(root.handlers[0].formatter, _JSONFormatter)

def test_configure_logging_json():
    configure_logging(log_format="json", log_level="INFO")
    root = logging.getLogger()
    assert root.level == logging.INFO
    assert len(root.handlers) > 0
    assert isinstance(root.handlers[0].formatter, _JSONFormatter)

def test_json_formatter():
    formatter = _JSONFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello world", args=(), exc_info=None
    )
    request_id_var.set("req-123")
    
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert parsed["msg"] == "hello world"
    assert parsed["request_id"] == "req-123"
    assert "ts" in parsed

def test_json_formatter_with_exc():
    formatter = _JSONFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        exc_info = sys.exc_info()
        
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0,
        msg="error happened", args=(), exc_info=exc_info
    )
    
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert "boom" in parsed["exc"]
    
def test_request_id_filter():
    # Setup text logging
    configure_logging(log_format="text")
    root = logging.getLogger()
    handler = root.handlers[0]
    
    request_id_var.set("req-test")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="msg", args=(), exc_info=None
    )
    
    # Filter should add request_id to record
    assert handler.filters[0].filter(record) is True
    assert record.request_id == "req-test"

# --- Core App Config Tests ---

def test_initialize_app():
    from core.app_config import initialize_app
    app_state = initialize_app()
    assert "axon_service" in app_state
    assert "memory_store" in app_state
    assert "security_config" in app_state
    assert "token_optimizer" in app_state
    assert "orchestrator" in app_state

def test_app_config_redis():
    import runpy
    import sys
    with patch.dict(os.environ, {"AXON_MEMORY_TYPE": "redis"}):
        # We must pop core.settings so runpy re-evaluates it and gets the new env var
        old_settings = sys.modules.pop("core.settings", None)
        try:
            result = runpy.run_path("core/app_config.py")
            from services.redis_memory_store import RedisMemoryStore
            assert isinstance(result["memory_store"], RedisMemoryStore)
        finally:
            if old_settings:
                sys.modules["core.settings"] = old_settings

def test_settings_no_dotenv():
    import sys
    import importlib
    import core.settings
    # Hide dotenv
    with patch.dict(sys.modules, {"dotenv": None}):
        importlib.reload(core.settings)
    # Restore
    importlib.reload(core.settings)

# --- Domain API Models Tests ---

def test_api_models():
    from domain.api_models import ProcessRequest, UpstreamProxyRequest, HealthResponse, SessionDeleteResponse
    
    req = ProcessRequest(inbound={"test": 1}, handler="echo", session_id="abc", target_model="gpt-4o")
    assert req.handler == "echo"
    
    proxy = UpstreamProxyRequest(method="POST", upstream_url="http://test.com", headers={"a": "b"}, data={"x": 1})
    assert proxy.method == "POST"
    
    health = HealthResponse(status="ok")
    assert health.status == "ok"
    
    sess = SessionDeleteResponse(status="deleted", session_id="abc")
    assert sess.session_id == "abc"
