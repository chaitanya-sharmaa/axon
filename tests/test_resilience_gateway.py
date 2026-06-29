import pytest
from fastapi.testclient import TestClient
from app import app
import httpx
import json
import copy

client = TestClient(app)

def test_json_healing_loop(monkeypatch):
    """
    Mock the upstream HTTPX client to return invalid JSON on attempt 1,
    and then capture if the second attempt includes the healing prompt.
    """
    call_count = 0
    captured_bodies = []

    async def mock_acompletion(*args, **kwargs):
        nonlocal call_count
        captured_bodies.append(copy.deepcopy(kwargs))
        call_count += 1
        
        class MockResponse:
            def __init__(self, content):
                self._content = content
            def model_dump(self):
                return self._content
                
        if call_count == 1:
            # Return malformed JSON string
            return MockResponse({
                "choices": [{"message": {"content": "{ \"key\": \"value\", "}}]
            })
        else:
            # Return valid JSON
            return MockResponse({
                "choices": [{"message": {"content": "{\"key\": \"value\"}"}}]
            })

    monkeypatch.setattr("litellm.acompletion", mock_acompletion)

    import uuid
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": f"hello {uuid.uuid4()}"}],
            "response_format": {"type": "json_object"}
        }
    )

    assert response.status_code == 200
    assert call_count == 2
    
    # The first request was the original payload
    print("Captured body:", captured_bodies[0])
    assert len(captured_bodies[0]["messages"]) == 1
    
    # The second request included the JSON Healing prompt
    second_request_messages = captured_bodies[1]["messages"]
    assert len(second_request_messages) == 3
    assert second_request_messages[1]["role"] == "assistant"
    assert second_request_messages[2]["role"] == "user"
    assert "Your previous output was invalid JSON" in second_request_messages[2]["content"]

def test_circuit_breaker(monkeypatch):
    """
    Mock the upstream SSE stream and ensure it terminates when cost exceeds max_spend.
    """
    class MockChunk:
        def __init__(self, content):
            class Delta:
                def __init__(self, c):
                    self.content = c
            class Choice:
                def __init__(self, d):
                    self.delta = d
            self.choices = [Choice(Delta(content))]
            self._content = content
        def model_dump_json(self, **kwargs):
            return f'{{"choices": [{{"delta": {{"content": "{self._content}"}}}}]}}'

    class MockStreamResp:
        def __init__(self):
            pass
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not hasattr(self, 'count'):
                self.count = 0
            if self.count >= 3:
                raise StopAsyncIteration
            self.count += 1
            return MockChunk(" expensive word")

    async def mock_acompletion(*args, **kwargs):
        return MockStreamResp()

    monkeypatch.setattr("litellm.acompletion", mock_acompletion)

    response = client.post(
        "/v1/chat/completions",
        headers={
            "Authorization": "Bearer test-key",
            "X-Axon-Max-Spend": "0.000001" # Extremely low budget to trigger breaker
        },
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True
        }
    )

    assert response.status_code == 200
    content = response.read().decode()
    assert "[AXON BUDGET EXCEEDED" in content
