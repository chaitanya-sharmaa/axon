"""Tokenizer factory: return a cached tokenizer for the given model name.

AnthropicClient is only instantiated when a ``claude-*`` model is first requested,
so users with OpenAI-only setups do not need ``ANTHROPIC_API_KEY`` set.
"""

import functools

import tiktoken


@functools.lru_cache(maxsize=32)
def get_tokenizer_for_model(model_name: str):
    """
    Returns a tokenizer object for the given model name.
    The tokenizer object is expected to have an ``encode`` method that returns a list
    of token IDs.
    """
    if model_name.startswith(("gpt", "text-")):
        # OpenAI models use tiktoken
        return tiktoken.encoding_for_model(model_name)

    if model_name.startswith("claude"):
        # Anthropic models: import and instantiate only on demand.
        from anthropic import Anthropic  # noqa: PLC0415
        client = Anthropic()
        return client.get_tokenizer()  # type: ignore

    # Unknown model — fall back to the GPT-4 / GPT-3.5-turbo encoding
    import logging  # noqa: PLC0415
    logging.warning(
        "Unknown model '%s'. Falling back to 'cl100k_base' tokenizer.", model_name
    )
    return tiktoken.get_encoding("cl100k_base")
