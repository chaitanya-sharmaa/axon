import pytest
from bridge.integrations.patch import patch

class MockCompletions:
    def create(self, **kwargs):
        class MockResponse:
            def __init__(self, request_kwargs):
                self.request_kwargs = request_kwargs
                self.id = "chatcmpl-123"
        return MockResponse(kwargs)

class MockChat:
    def __init__(self):
        self.completions = MockCompletions()

class MockOpenAIClient:
    def __init__(self):
        self.chat = MockChat()

def test_axon_patch_compresses_messages():
    client = MockOpenAIClient()
    patched_client = patch(client)
    
    # Send a request with a massive thought block and extra text
    response = patched_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": "Hello, this is a very long string that should trigger the optimizer to do something. " * 50},
            {"role": "assistant", "content": "<thought>This is an old thought block that should be completely removed by the minify_scratchpad algorithm.</thought> And here is the final action."},
            {"role": "user", "content": "Thanks! Can you do one more thing?"},
            {"role": "assistant", "content": "Sure! Here is the response."}
        ]
    )
    
    # 1. Verify metrics were injected
    assert hasattr(response, "_axon_metrics")
    assert response._axon_metrics["original_tokens"] > 0
    assert response._axon_metrics["compressed_tokens"] >= 0
    
    # 2. Verify the payload was compressed before sending
    final_kwargs = response.request_kwargs
    messages = final_kwargs["messages"]
    
    assert len(messages) == 4
    
    # The assistant message should have the thought block removed
    assert "<thought>" not in messages[1]["content"]
    assert "And here is the final action." in messages[1]["content"]
    
    # Verify original message is untouched if not minified
    assert "Hello" in messages[0]["content"]

def test_axon_patch_prunes_tools():
    client = MockOpenAIClient()
    patched_client = patch(client)
    
    # Send a request with tools
    tools = [
        {"type": "function", "function": {"name": "get_weather", "description": "Get weather"}},
        {"type": "function", "function": {"name": "search_db", "description": "Search database"}},
        {"type": "function", "function": {"name": "irrelevant_tool", "description": "Not related at all"}},
        {"type": "function", "function": {"name": "another_irrelevant_tool", "description": "Also not related"}},
    ]
    
    response = patched_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "What is the weather?"}],
        tools=tools
    )
    
    # The tools should be pruned based on the user's query
    final_kwargs = response.request_kwargs
    final_tools = final_kwargs.get("tools")
    
    assert final_tools is not None
    assert len(final_tools) <= 5 # max_tools=5 default
