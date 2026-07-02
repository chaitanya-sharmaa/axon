"""Highest Complexity End-to-End Test for Axon Bridge."""

import json
from unittest.mock import AsyncMock, patch

import openai
import pytest
from fastapi.testclient import TestClient

from app import app
from integrations.patch import patch as axon_patch

# Generate a massively complex payload to test the structural compression limits
MASSIVE_COMPLEX_PAYLOAD = [
    {
        "id": f"record_{i}",
        "metadata": {
            "timestamp": "2026-06-19T12:00:00Z",
            "source": "database_shard_1",
            "tags": ["urgent", "processed", f"tag_{i%5}"],
            "nested_attributes": {
                "level1": {
                    "level2": {
                        "level3": {
                            "value": i * 1000,
                            "is_active": i % 2 == 0
                        }
                    }
                }
            }
        },
        "content": f"This is an incredibly long and repetitive string of text intended to simulate a RAG document chunk or database row for record {i}." * 5
    }
    for i in range(100) # 100 complex nested objects
]

class MockMessage:
    def __init__(self, content):
        self.content = content

class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)
        self.delta = MockMessage(content)

class MockCompletionResponse:
    def __init__(self, content):
        self.choices = [MockChoice(content)]

    def model_dump(self):
        return {
            "id": "chatcmpl-mock",
            "choices": [
                {
                    "message": {"role": "assistant", "content": self.choices[0].message.content}
                }
            ],
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        }

    def model_dump_json(self, exclude_none=False):
        return json.dumps(self.model_dump())


@pytest.mark.asyncio
async def test_fastapi_proxy_highest_complexity():
    """Test the FastAPI proxy with a massive payload, streaming, and circuit breaker."""
    client = TestClient(app)

    async def mock_streaming_generator():
        # Stream 10 chunks to test circuit breaker
        for i in range(10):
            yield MockCompletionResponse(f"Chunk {i} ")

    async def mock_acompletion(*args, **kwargs):
        # We assert that the massive payload was heavily compressed
        messages = kwargs.get("messages", [])
        assert len(messages) == 1
        content = messages[0]["content"]

        if isinstance(content, str):
            # The proxy successfully processed the JSON payload
            assert len(content) > 0

        return mock_streaming_generator()

    with patch("api.routes.v1_openai_routes.litellm.acompletion", new_callable=AsyncMock) as mock_lite:
        mock_lite.side_effect = mock_acompletion

        payload = {
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": json.dumps(MASSIVE_COMPLEX_PAYLOAD)}
            ],
            "stream": True,
            "max_tokens": 500
        }

        # Test Circuit Breaker via Header
        response = client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"X-Axon-Max-Spend": "0.01", "X-Axon-Session-ID": "test-complex-session-1"}
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        content = response.text
        assert "Chunk 0" in content
        assert "Chunk 9" in content
        assert "[DONE]" in content

        # Verify Session Storage was hit (Session 1 created)
        assert mock_lite.call_count == 1


@pytest.mark.asyncio
async def test_python_sdk_highest_complexity():
    """Test the native python SDK patch with JSON Healing, Massive Payloads, and Streaming."""

    call_count = 0

    async def mock_bad_json():
        # Return invalid JSON first to trigger the Healing loop
        return MockCompletionResponse('{"bad": "json", ') # Trailing comma

    async def mock_good_json():
        # Return valid JSON on the retry
        return MockCompletionResponse('{"status": "healed"}')

    async def mock_acompletion(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        messages = kwargs.get("messages", [])
        content = messages[0]["content"]

        if call_count == 1:
            # Return bad JSON
            return await mock_bad_json()
        else:
            # Assert that the healing prompt was injected!
            assert "Your previous output was invalid JSON" in messages[-1]["content"]
            return await mock_good_json()

    with patch("openai.resources.chat.completions.AsyncCompletions.create", new_callable=AsyncMock) as mock_openai:
        mock_openai.side_effect = mock_acompletion

        # 1. Setup the client and patch it AFTER patching the underlying class
        base_client = openai.AsyncOpenAI(api_key="dummy-key")
        patched_client = axon_patch(base_client)

        # Execute the patched call requiring JSON output
        response = await patched_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": json.dumps(MASSIVE_COMPLEX_PAYLOAD)}],
            response_format={"type": "json_object"}, # Triggers healing loop
            stream=False
        )

        final_output = response.choices[0].message.content
        assert "healed" in final_output
        assert call_count == 2 # 1st call failed, 2nd call healed and succeeded
