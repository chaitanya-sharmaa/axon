"""Tests for Asynchronous Swarm Routing."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


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
            "model": "gpt-4o"
        }

    def model_dump_json(self, exclude_none=False):
        return json.dumps(self.model_dump())


@pytest.mark.asyncio
async def test_swarm_completions_non_streaming():
    """Test fan-out and synthesis for non-streaming swarm completions."""

    # Mock litellm.acompletion
    async def mock_acompletion(*args, **kwargs):
        model = kwargs.get("model")
        if model == "model-a":
            return MockCompletionResponse("Answer from A")
        elif model == "model-b":
            return MockCompletionResponse("Answer from B")
        elif model == "gpt-4o":
            # This is the synthesizer
            messages = kwargs.get("messages", [])
            sys_msg = messages[0]["content"]
            assert "Answer from A" in sys_msg
            assert "Answer from B" in sys_msg
            return MockCompletionResponse("Synthesized Final Answer")
        return MockCompletionResponse("Unknown")

    with patch("api.routes.v1_swarm_routes.litellm.acompletion", new_callable=AsyncMock) as mock_lite:
        mock_lite.side_effect = mock_acompletion

        payload = {
            "messages": [
                {"role": "user", "content": "How do I reverse a string?"}
            ],
            "models": ["model-a", "model-b"],
            "synthesizer_model": "gpt-4o",
            "stream": False
        }

        response = client.post("/v1/swarm/completions", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["choices"][0]["message"]["content"] == "Synthesized Final Answer"

        # Verify it made 3 calls (2 fan-out, 1 synthesize)
        assert mock_lite.call_count == 3


@pytest.mark.asyncio
async def test_swarm_completions_streaming():
    """Test streaming output from the synthesizer."""

    async def mock_streaming_generator():
        yield MockCompletionResponse("Synth ")
        yield MockCompletionResponse("Stream!")

    async def mock_acompletion(*args, **kwargs):
        model = kwargs.get("model")
        if model == "model-a":
            return MockCompletionResponse("A")
        elif model == "model-b":
            return MockCompletionResponse("B")
        elif model == "gpt-4o":
            return mock_streaming_generator()

    with patch("api.routes.v1_swarm_routes.litellm.acompletion", new_callable=AsyncMock) as mock_lite:
        mock_lite.side_effect = mock_acompletion

        payload = {
            "messages": [
                {"role": "user", "content": "Hello!"}
            ],
            "models": ["model-a", "model-b"],
            "synthesizer_model": "gpt-4o",
            "stream": True
        }

        response = client.post("/v1/swarm/completions", json=payload)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        content = response.text
        assert "data: " in content
        assert "Synth " in content
        assert "Stream!" in content
        assert "[DONE]" in content
