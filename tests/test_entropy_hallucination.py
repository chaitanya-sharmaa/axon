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
