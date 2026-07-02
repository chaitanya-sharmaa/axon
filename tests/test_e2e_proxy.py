import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Ensure we have the app loaded
from app import app
from core.settings import settings

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == settings.app_version


@patch("api.routes.v1_openai_routes.bridge_service.process_chat_completion")
def test_e2e_proxy_chat_completion(mock_process):
    # Mock the return value of process_chat_completion
    # process_chat_completion is async, but TestClient handles the event loop.
    # We need an AsyncMock since process_chat_completion is an async function.
    import asyncio
    
    async def mock_coro(*args, **kwargs):
        from api.routes.v1_openai_routes import ChatCompletionResponse
        return ChatCompletionResponse(
            id="chatcmpl-mock",
            object="chat.completion",
            created=1234567890,
            model="gpt-4o",
            choices=[{
                "index": 0,
                "message": {"role": "assistant", "content": "Mocked response!"},
                "finish_reason": "stop"
            }],
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        ), {"x-axon-metrics": json.dumps({"original_tokens": 10, "compressed_tokens": 5, "savings_pct": 50})}
        
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
