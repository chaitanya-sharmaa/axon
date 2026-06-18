from unittest.mock import patch, MagicMock
from services.tokenizer_factory import get_tokenizer_for_model

def test_get_tokenizer_openai():
    tokenizer = get_tokenizer_for_model("gpt-4o")
    # Should be tiktoken encoding
    assert hasattr(tokenizer, "encode")

@patch("anthropic.Anthropic")
def test_get_tokenizer_anthropic(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client
    mock_tokenizer = MagicMock()
    mock_client.get_tokenizer.return_value = mock_tokenizer
    
    tokenizer = get_tokenizer_for_model("claude-3-opus")
    assert tokenizer == mock_tokenizer

def test_get_tokenizer_fallback():
    tokenizer = get_tokenizer_for_model("unknown-model")
    # Should fall back to cl100k_base which has encode
    assert hasattr(tokenizer, "encode")
