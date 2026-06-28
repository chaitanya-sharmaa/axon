from unittest.mock import patch, MagicMock
from services.tokenizer_factory import get_tokenizer_for_model

def test_get_tokenizer_openai():
    tokenizer = get_tokenizer_for_model("gpt-4o")
    # Should be tiktoken encoding
    assert hasattr(tokenizer, "encode")

def test_get_tokenizer_anthropic():
    import sys
    mock_anthropic_module = MagicMock()
    mock_client = MagicMock()
    mock_anthropic_module.Anthropic.return_value = mock_client
    mock_tokenizer = MagicMock()
    mock_client.get_tokenizer.return_value = mock_tokenizer
    
    with patch.dict(sys.modules, {'anthropic': mock_anthropic_module}):
        from services.tokenizer_factory import get_tokenizer_for_model
        tokenizer = get_tokenizer_for_model("claude-3-opus")
        assert tokenizer == mock_tokenizer

def test_get_tokenizer_fallback():
    tokenizer = get_tokenizer_for_model("unknown-model")
    # Should fall back to cl100k_base which has encode
    assert hasattr(tokenizer, "encode")
