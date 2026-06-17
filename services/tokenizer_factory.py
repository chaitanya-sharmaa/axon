import tiktoken
from anthropic import Anthropic
import functools

# Cache for tokenizer instances
_tokenizer_cache = {}

@functools.lru_cache(maxsize=None) # Cache the client instance
def _get_anthropic_client():
    """
    Initializes and caches the Anthropic client.
    This assumes ANTHROPIC_API_KEY is set in environment variables.
    """
    return Anthropic()

def get_tokenizer_for_model(model_name: str):
    """
    Returns a tokenizer object for the given model name.
    The tokenizer object is expected to have an `encode` method that returns a list of token IDs.
    """
    if model_name not in _tokenizer_cache:
        if model_name.startswith("gpt") or model_name.startswith("text-"):
            # OpenAI models use tiktoken
            _tokenizer_cache[model_name] = tiktoken.encoding_for_model(model_name)
        elif model_name.startswith("claude"):
            # Anthropic models use their own tokenizer
            client = _get_anthropic_client()
            _tokenizer_cache[model_name] = client.get_tokenizer()
        else:
            print(f"Warning: Unknown model '{model_name}'. Falling back to 'cl100k_base' tokenizer.")
            _tokenizer_cache[model_name] = tiktoken.get_encoding("cl100k_base")
    return _tokenizer_cache[model_name]