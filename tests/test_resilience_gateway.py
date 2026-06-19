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

    class MockResponse:
        def __init__(self, content, status_code=200):
            self._content = content
            self.status_code = status_code

        def json(self):
            return self._content
            
        def raise_for_status(self):
            pass

    async def mock_post(self_obj, url, headers=None, json=None, **kwargs):
        nonlocal call_count
        captured_bodies.append(copy.deepcopy(json))
        call_count += 1
        
        if call_count == 1:
            # Return malformed JSON string inside the valid OpenAI response envelope
            return MockResponse({
                "choices": [{"message": {"content": "{ \"key\": \"value\", "}}]
            })
        else:
            # Return valid JSON
            return MockResponse({
                "choices": [{"message": {"content": "{\"key\": \"value\"}"}}]
            })

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hello"}],
            "response_format": {"type": "json_object"}
        }
    )

    assert response.status_code == 200
    assert call_count == 2
    
    # The first request was the original payload
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
    class MockStreamResp:
        def __init__(self):
            pass
            
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
        def raise_for_status(self):
            pass
            
        async def aiter_lines(self):
            yield 'data: {"choices": [{"delta": {"content": " expensive word"}}]}'
            yield 'data: {"choices": [{"delta": {"content": " expensive word"}}]}'
            yield 'data: {"choices": [{"delta": {"content": " expensive word"}}]}'
            
    class MockStreamContext:
        def __init__(self):
            pass
        async def __aenter__(self):
            return MockStreamResp()
        async def __aexit__(self, *args):
            pass

    def mock_stream(self_obj, method, url, **kwargs):
        return MockStreamContext()

    monkeypatch.setattr("httpx.AsyncClient.stream", mock_stream)

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
