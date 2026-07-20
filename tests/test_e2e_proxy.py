import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Ensure we have the app loaded
from axon.app import app
from axon.core.settings import settings

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == settings.app_version


@patch("axon.api.routes.v1_openai_routes.litellm.acompletion")
def test_e2e_proxy_chat_completion(mock_process):
    import asyncio
    
    async def mock_coro(*args, **kwargs):
        class MockChoice:
            def __init__(self):
                self.message = type('obj', (object,), {'role': 'assistant', 'content': 'Mocked response!'})()
        
        class MockResponse:
            def __init__(self):
                self.id = "chatcmpl-mock"
                self.choices = [MockChoice()]
                self.usage = type('obj', (object,), {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15})()
            def model_dump(self, **kwargs):
                return {
                    "id": self.id,
                    "choices": [{"message": {"role": "assistant", "content": "Mocked response!"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
                }
        return MockResponse()
        
    mock_process.side_effect = mock_coro

    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Hello, world! This is an E2E test."}
        ]
    }
    
    # We bypass auth by either not enforcing it or setting the right headers if required
    headers = {}
    if settings.require_api_key:
        headers["X-API-Key"] = settings.api_key or "test"

    response = client.post("/v1/chat/completions", json=payload, headers=headers)
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    assert data["choices"][0]["message"]["content"] == "Mocked response!"
    
    # Check headers
    assert "x-axon-metrics" in response.headers
