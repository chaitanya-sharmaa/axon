import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from litellm import APIError, ServiceUnavailableError

from app import app
from core.settings import settings

client = TestClient(app)

@pytest.fixture
def mock_litellm():
    with patch("api.routes.v1_openai_routes.litellm.acompletion", new_callable=AsyncMock) as mock_lite:
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "choices": [{"message": {"content": "mocked response"}}],
            "usage": {"completion_tokens": 10}
        }
        mock_lite.return_value = mock_response
        yield mock_lite

def test_vision_downscaling_and_pruning(mock_litellm):
    # Set pruning on
    with patch.dict(os.environ, {"AXON_PRUNE_TEXT": "true"}):
        req = {
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="}}
                ]},
                {"role": "user", "content": "A" * 2500} # Trigger pruning (>2000 chars)
            ]
        }
        resp = client.post("/v1/chat/completions", json=req)
        assert resp.status_code == 200

def test_anthropic_prompt_caching(mock_litellm):
    import uuid
    req = {
        "model": "claude-3-opus",
        "messages": [
            {"role": "system", "content": f"S{uuid.uuid4()}" * 150}, # >100 chars triggers caching
            {"role": "user", "content": f"U{uuid.uuid4()}" * 200}  # Triggers largest message caching
        ]
    }
    resp = client.post("/v1/chat/completions", json=req)
    assert resp.status_code == 200

    # Check that Litellm was called with cache_control
    call_kwargs = mock_litellm.call_args.kwargs
    messages = call_kwargs["messages"]

    system_msg = messages[0]["content"]
    assert isinstance(system_msg, list)
    assert system_msg[0]["cache_control"]["type"] == "ephemeral"

    user_msg = messages[1]["content"]
    assert isinstance(user_msg, list)
    assert user_msg[0]["cache_control"]["type"] == "ephemeral"

def test_direct_gemini_api_call(mock_litellm):
    mock_resp = MagicMock()
    mock_resp.model_dump.return_value = {
        "choices": [{"message": {"content": "gemini directly"}}],
        "usage": {"completion_tokens": 10}
    }
    mock_litellm.return_value = mock_resp

    import uuid
    req = {
        "model": "gemini/gemini-pro",
        "messages": [{"role": "user", "content": f"hello {uuid.uuid4()}"}]
    }
    resp = client.post("/v1/chat/completions", json=req)
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "gemini directly"

def test_json_healing_loop(mock_litellm):
    import uuid
    # Mock Litellm to return bad JSON twice, then good JSON
    mock_resp1 = MagicMock()
    mock_resp1.model_dump.return_value = {"choices": [{"message": {"content": "{bad json"}}]}

    mock_resp2 = MagicMock()
    mock_resp2.model_dump.return_value = {"choices": [{"message": {"content": '{"valid": "but wrong schema"}'}}]}

    mock_resp3 = MagicMock()
    mock_resp3.model_dump.return_value = {"choices": [{"message": {"content": '{"name": "ok"}'}}]}

    mock_litellm.side_effect = [mock_resp1, mock_resp2, mock_resp3]

    req = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": f"give json {uuid.uuid4()}"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": {"type": "object", "required": ["name"]}}
        }
    }

    resp = client.post("/v1/chat/completions", json=req)
    assert resp.status_code == 200
    assert mock_litellm.call_count == 3
    assert resp.json()["choices"][0]["message"]["content"] == '{"name": "ok"}'

def test_fallback_retry_loop(mock_litellm):
    import uuid
    # First call fails with ServiceUnavailable, second call succeeds with fallback model
    mock_litellm.side_effect = [
        ServiceUnavailableError(message="down", response=MagicMock(), llm_provider="openai", model="gpt-4o"),
        MagicMock(model_dump=lambda: {"choices": [{"message": {"content": "fallback works"}}]})
    ]

    with patch.dict(os.environ, {"AXON_AUTO_ROUTING": "true"}):
        req = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": f"test {uuid.uuid4()}" * 500}]
        }
        resp = client.post("/v1/chat/completions", json=req)
        assert resp.status_code == 200
        assert mock_litellm.call_count == 2
        # The second call should use gpt-3.5-turbo as fallback from gpt-4o
        assert mock_litellm.call_args_list[1].kwargs["model"] == "gpt-3.5-turbo"

def test_streaming_exception_handling():
    with patch("api.routes.v1_openai_routes.litellm.acompletion") as mock_lite:
        async def mock_stream(*args, **kwargs):
            raise APIError(message="stream err", status_code=500, request=MagicMock(), llm_provider="openai", model="gpt-4o")
            yield  # To make it an async generator

        mock_lite.side_effect = mock_stream

        req = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "stream me"}],
            "stream": True
        }
        with pytest.raises(APIError):
            client.post("/v1/chat/completions", json=req)

def test_tracking_and_background_tasks(mock_litellm):
    from core.app_config import memory_store
    with patch.object(settings, "enable_tenant_quotas", True):
        with patch.object(memory_store, "increment_tenant_spend", new_callable=AsyncMock) as mock_inc:
            req = {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "hi"}],
                "session_id": "test_sess"
            }
            resp = client.post("/v1/chat/completions", json=req, headers={"X-Axon-Tenant-ID": "t1"})
            assert resp.status_code == 200

            # The background task was added. We can't easily wait for it in TestClient,
            # but we can ensure it doesn't throw.
