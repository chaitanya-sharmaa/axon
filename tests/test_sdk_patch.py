import pytest
from integrations.patch import patch

class MockCompletions:
    def create(self, **kwargs):
        class MockResponse:
            def __init__(self, request_kwargs):
                self.request_kwargs = request_kwargs
                self.id = "chatcmpl-123"
                self.choices = []

            def _add_choice(self, content):
                class Msg:
                    def __init__(self, c):
                        self.content = c
                class Choice:
                    def __init__(self, c):
                        self.message = Msg(c)
                self.choices.append(Choice(content))

        # Handle stream mocked return
        if kwargs.get("stream"):
            class MockStream:
                def __init__(self, kwargs):
                    self.request_kwargs = kwargs
                def __iter__(self):
                    yield "chunk1"
                    yield "chunk2"
            return MockStream(kwargs)
            
        resp = MockResponse(kwargs)
        
        # Simulate JSON hallucination for testing
        if kwargs.get("response_format", {}).get("type") == "json_object":
            if "Fix this specific syntax error" not in str(kwargs.get("messages", [])):
                resp._add_choice("{ bad_json: ")
            else:
                resp._add_choice('{"fixed": "json"}')
        else:
            resp._add_choice("normal text")
            
        return resp

class MockChat:
    def __init__(self):
        self.completions = MockCompletions()

class MockAsyncCompletions:
    async def create(self, **kwargs):
        class MockResponse:
            def __init__(self, request_kwargs):
                self.request_kwargs = request_kwargs
                self.id = "chatcmpl-async-123"
        return MockResponse(kwargs)

class MockChat:
    def __init__(self):
        self.completions = MockCompletions()

class MockAsyncChat:
    def __init__(self):
        self.completions = MockAsyncCompletions()

class MockOpenAIClient:
    def __init__(self):
        self.chat = MockChat()

class MockAsyncOpenAIClient:
    def __init__(self):
        self.chat = MockAsyncChat()

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

@pytest.mark.asyncio
async def test_axon_patch_async():
    client = MockAsyncOpenAIClient()
    patched_client = patch(client)
    
    response = await patched_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello Async!"}]
    )
    
    assert hasattr(response, "_axon_metrics")
    assert response.id == "chatcmpl-async-123"

def test_axon_patch_stream():
    client = MockOpenAIClient()
    patched_client = patch(client)
    
    response = patched_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Stream me"}],
        stream=True
    )
    
    assert hasattr(response, "_axon_metrics")
    chunks = list(response)
    assert chunks == ["chunk1", "chunk2"]

def test_axon_patch_json_healing():
    client = MockOpenAIClient()
    patched_client = patch(client)
    
    response = patched_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Give me JSON"}],
        response_format={"type": "json_object"}
    )
    
    assert hasattr(response, "_axon_metrics")
    
    # Verify the healing prompt was injected into the messages
    final_kwargs = response.request_kwargs
    messages = final_kwargs["messages"]
    
    assert len(messages) == 3
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "{ bad_json: "
    assert "Fix this specific syntax error" in messages[2]["content"]
