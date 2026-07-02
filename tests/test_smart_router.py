from unittest.mock import patch

from services.smart_router import (
    analyze_complexity,
    fallback_model,
    get_load_balanced_key,
    route_model,
)


def test_get_load_balanced_key():
    # Empty / single key
    assert get_load_balanced_key("") == ""
    assert get_load_balanced_key("sk-123") == "sk-123"

    # Multiple keys
    key_str = "sk-1, sk-2, sk-3 "
    assert get_load_balanced_key(key_str) == "sk-1"
    assert get_load_balanced_key(key_str) == "sk-2"
    assert get_load_balanced_key(key_str) == "sk-3"
    assert get_load_balanced_key(key_str) == "sk-1"

def test_analyze_complexity():
    assert analyze_complexity("") == "low"
    assert analyze_complexity("hello") == "low"

    # High complexity keywords
    assert analyze_complexity("analyze this data") == "high"
    assert analyze_complexity("please implement this function") == "high"
    assert analyze_complexity("comprehensive review") == "high"

    # Code markers
    assert analyze_complexity("Here is some code ```python\nprint(1)```") == "high"
    assert analyze_complexity("def my_func(): pass") == "high"
    assert analyze_complexity("class User:") == "high"
    assert analyze_complexity("SELECT * FROM table") == "high"

    # Long text
    long_text = "a " * 2001
    assert analyze_complexity(long_text) == "high"

@patch("services.smart_router.settings")
@patch("services.smart_router.classify_intent")
def test_route_model(mock_classify, mock_settings):
    mock_settings.enable_semantic_routing = False
    assert route_model("gpt-4o", 100) == "gpt-4o"

    mock_settings.enable_semantic_routing = True

    # Test low complexity -> lite
    mock_classify.return_value = "low"
    assert route_model("gpt-4o", 100) == "gpt-4o-mini"
    assert route_model("claude-3-5-sonnet", 100) == "claude-3-5-haiku-20241022"
    assert route_model("gemini-2.5-pro", 100) == "gemini-2.5-flash"
    assert route_model("ollama/qwen2.5:14b", 100) == "ollama/llama3:latest"
    assert route_model("unknown-model", 100) == "unknown-model"

    # Test high complexity -> pro
    mock_classify.return_value = "high"
    assert route_model("gpt-4o-mini", 100) == "gpt-4o"
    assert route_model("claude-3-5-haiku", 100) == "claude-3-5-sonnet-20241022"
    assert route_model("gemini/gemini-2.5-flash", 100) == "gemini/gemini-2.5-pro"
    assert route_model("ollama/llama3:latest", 100) == "ollama/qwen2.5:14b"
    assert route_model("unknown-model", 100) == "unknown-model"

def test_fallback_model():
    assert fallback_model("gpt-4o") == "gpt-4-turbo"
    assert fallback_model("unknown-model") == "unknown-model"
