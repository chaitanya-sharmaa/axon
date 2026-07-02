import os
import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import app

os.environ["OPENAI_API_KEY"] = "dummy"
os.environ["AXON_REQUIRE_API_KEY"] = "false"

client = TestClient(app)

def test_shannon_entropy_hallucination_guard():
    class MockResponse:
        def model_dump(self):
            # Entropy = 4 * (0.25 * 2) = 2.0 (since log2(0.25) is -2)
            logprobs = {
                "content": [
                    {
                        "token": "a",
                        "top_logprobs": [
                            {"token": "a", "logprob": -1.38},
                            {"token": "b", "logprob": -1.38},
                            {"token": "c", "logprob": -1.38},
                            {"token": "d", "logprob": -1.38},
                        ]
                    }
                ]
            }
            return {
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "gpt-4o",
                "choices": [{"message": {"role": "assistant", "content": "hello"}, "logprobs": logprobs}]
            }

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = MockResponse()

        req_body = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Trigger hallucination please"}],
            "temperature": 0.0
        }

        # This will exhaust the attempts and eventually fail 502
        response = client.post("/v1/chat/completions", json=req_body)

        # Verify that it tried multiple times because of the Hallucination error
        assert mock_acompletion.call_count >= 3


def test_shannon_entropy_NOT_enabled_for_ollama():
    import uuid
    """BUG FIX: Verify logprobs are NOT injected for ollama/ models (unsupported natively)."""
    class MockResponse:
        def model_dump(self):
            return {
                "id": "chatcmpl-ollama-123",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "ollama/llama3",
                "choices": [{"message": {"role": "assistant", "content": "hello ollama"}}]
            }

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion, \
         patch("services.semantic_cache.SemanticCache.check_cache", new_callable=AsyncMock) as mock_cache:
        mock_acompletion.return_value = MockResponse()
        mock_cache.return_value = (None, None)

        req_body = {
            "model": "ollama/llama3",
            "messages": [{"role": "user", "content": f"hello ollama {uuid.uuid4()}"}],
            "temperature": 0.0
        }

        response = client.post("/v1/chat/completions", json=req_body)

        assert mock_acompletion.call_count == 1
        assert response.status_code == 200

        # Verify logprobs were NOT injected
        call_kwargs = mock_acompletion.call_args
        assert "logprobs" not in call_kwargs.kwargs, "logprobs should NOT be injected for ollama/"


def test_logprobs_not_injected_for_gemini():
    import uuid
    """Verify logprobs are NOT injected for Gemini (which rejects the param)."""
    class MockResponse:
        def model_dump(self):
            return {
                "id": "gemini-123",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "gemini/gemini-1.5-flash",
                "choices": [{"message": {"role": "assistant", "content": "hello gemini"}}]
            }

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion, \
         patch("services.semantic_cache.SemanticCache.check_cache", new_callable=AsyncMock) as mock_cache:
        mock_acompletion.return_value = MockResponse()
        mock_cache.return_value = (None, None)

        req_body = {
            "model": "gemini/gemini-1.5-flash",
            "messages": [{"role": "user", "content": f"hello gemini {uuid.uuid4()}"}],
            "temperature": 0.0
        }

        response = client.post("/v1/chat/completions", json=req_body)
        assert response.status_code == 200

        call_kwargs = mock_acompletion.call_args
        assert "logprobs" not in call_kwargs.kwargs, "logprobs must NOT be injected for Gemini"
        # And drop_params should be True so other unsupported params are cleaned safely
        assert call_kwargs.kwargs.get("drop_params") is True
