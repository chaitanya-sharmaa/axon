import pytest
import math
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app import app
import os
import time

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


def test_shannon_entropy_enabled_for_ollama():
    """BUG FIX: Verify logprobs are now injected for ollama/ models (not just gpt)."""
    class MockResponse:
        def model_dump(self):
            # Low entropy response: confident, no hallucination
            logprobs = {
                "content": [
                    {
                        "token": "hello",
                        "top_logprobs": [
                            {"token": "hello", "logprob": -0.01},  # ~99% confident
                        ]
                    }
                ]
            }
            return {
                "id": "chatcmpl-ollama-123",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "ollama/llama3",
                "choices": [{"message": {"role": "assistant", "content": "hello"}, "logprobs": logprobs}]
            }

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = MockResponse()

        req_body = {
            "model": "ollama/llama3",
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.0
        }

        response = client.post("/v1/chat/completions", json=req_body)

        # Should succeed with exactly 1 call (low entropy, no healing triggered)
        assert mock_acompletion.call_count == 1
        assert response.status_code == 200

        # Verify logprobs were actually injected into the call
        call_kwargs = mock_acompletion.call_args
        assert call_kwargs.kwargs.get("logprobs") is True, "logprobs should be injected for ollama/"
        # Verify drop_params was False (not silently killing logprobs)
        assert call_kwargs.kwargs.get("drop_params") is False, "drop_params must be False when logprobs is enabled"


def test_logprobs_not_injected_for_gemini():
    """Verify logprobs are NOT injected for Gemini (which rejects the param)."""
    class MockResponse:
        def model_dump(self):
            return {
                "id": "gemini-123",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "gemini/gemini-1.5-flash",
                "choices": [{"message": {"role": "assistant", "content": "hello"}, "logprobs": None}]
            }

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = MockResponse()

        req_body = {
            "model": "gemini/gemini-1.5-flash",
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.0
        }

        response = client.post("/v1/chat/completions", json=req_body)
        assert response.status_code == 200

        call_kwargs = mock_acompletion.call_args
        assert "logprobs" not in call_kwargs.kwargs, "logprobs must NOT be injected for Gemini"
        # And drop_params should be True so other unsupported params are cleaned safely
        assert call_kwargs.kwargs.get("drop_params") is True
