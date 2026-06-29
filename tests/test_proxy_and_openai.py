import pytest
from unittest.mock import patch, AsyncMock
import httpx
import core.app_config

# --- Proxy Routes Tests ---

def test_proxy_upstream_forbidden(client):
    import core.app_config
    with patch.object(core.app_config.security_config, "allow_all_domains", False):
        req = {
            "upstream_url": "https://not-allowed.com/api",
            "method": "POST"
        }
        res = client.post("/proxy/upstream", json=req)
        assert res.status_code == 403
        assert "Domain not permitted" in res.json()["detail"]

def test_proxy_upstream_invalid_method(client):
    req = {
        "upstream_url": "https://api.github.com/test",
        "method": "INVALID"
    }
    res = client.post("/proxy/upstream", json=req)
    assert res.status_code == 400

def test_proxy_upstream_success(client, mock_httpx_request):
    mock_httpx_request.return_value = httpx.Response(
        200, request=httpx.Request("POST", "http://testserver"), headers={"content-type": "application/json"},
        content=b'{"mock": "response"}'
    )
    
    req = {
        "upstream_url": "https://api.github.com/test",
        "method": "POST",
        "data": {"req": 1},
        "session_id": "proxy_sess"
    }
    res = client.post("/proxy/upstream", json=req)
    assert res.status_code == 200
    data = res.json()
    assert "compact_text" in data
    assert data["upstream"]["status"] == 200

def test_proxy_upstream_httpx_error(client, mock_httpx_request):
    mock_httpx_request.side_effect = httpx.RequestError("Network down")
    req = {
        "upstream_url": "https://api.github.com/test",
        "method": "GET"
    }
    res = client.post("/proxy/upstream", json=req)
    assert res.status_code == 502

# --- OpenAI Routes Tests ---

@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
def test_list_models(mock_get, client):
    mock_get.return_value = httpx.Response(200, request=httpx.Request("POST", "http://testserver"), json={"data": [{"id": "gpt-4"}]})
    res = client.get("/v1/models")
    assert res.status_code == 200
    assert res.json()["data"][0]["id"] == "gpt-4"

@patch("httpx.AsyncClient.get", new_callable=AsyncMock)
def test_list_models_error(mock_get, client):
    mock_get.side_effect = httpx.RequestError("Error")
    res = client.get("/v1/models")
    assert res.status_code == 502

def test_chat_completions(client, mock_litellm_acompletion):
    class MockResponse:
        def model_dump(self):
            return {"id": "chatcmpl-123", "choices": [{"message": {"content": "ok"}}]}
    mock_litellm_acompletion.return_value = MockResponse()

    req = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Short message"},
            {"role": "user", "content": "Long message over 50 chars that can be compressed " * 3}
        ]
    }
    res = client.post("/v1/chat/completions", json=req)
    assert res.status_code == 200
    assert res.json()["id"] == "chatcmpl-123"
    assert "x-axon-metrics" in res.headers

def test_chat_completions_stream(client):
    async def mock_stream_openai(*args, **kwargs):
        yield "data: {\"id\": \"1\"}\n\n"
        yield "data: [DONE]\n\n"
        
    with patch("api.routes.v1_openai_routes._stream_openai", new=mock_stream_openai):
        req = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True
        }
        res = client.post("/v1/chat/completions", json=req)
        assert res.status_code == 200
        content = res.content.decode()
        assert "data:" in content
        assert "x-axon-metrics" in res.headers

@patch("api.routes.v1_openai_routes.litellm.aembedding", new_callable=AsyncMock)
def test_embeddings(mock_aembedding, client):
    class MockResponse:
        def model_dump(self):
            return {"data": [{"embedding": []}]}
    mock_aembedding.return_value = MockResponse()

    req = {
        "model": "text-embedding-3-small",
        "input": "test"
    }
    res = client.post("/v1/embeddings", json=req)
    assert res.status_code == 200
    assert "data" in res.json()

@patch("api.routes.v1_openai_routes.litellm.aembedding", new_callable=AsyncMock)
def test_embeddings_error(mock_aembedding, client):
    mock_aembedding.side_effect = Exception("Error")
    req = {"model": "text-embedding-3", "input": "test"}
    res = client.post("/v1/embeddings", json=req)
    assert res.status_code == 502

# --- Middleware Tests ---

def test_request_id_middleware(client):
    res = client.get("/health/live", headers={"X-Request-ID": "test-id-123"})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == "test-id-123"
    
    # Auto-generate
    res2 = client.get("/health/live")
    assert res2.status_code == 200
    assert "X-Request-ID" in res2.headers
    assert len(res2.headers["X-Request-ID"]) > 10

def test_proxy_upstream_invalid_api_key(client):
    import core.app_config
    with patch.object(core.app_config.security_config, "require_api_key", True), \
         patch.object(core.app_config.security_config, "api_key", "secret"):
        req = {"upstream_url": "https://api.github.com/test", "method": "POST"}
        res = client.post("/proxy/upstream", json=req, headers={"X-API-Key": "wrong"})
        assert res.status_code == 401

def test_proxy_upstream_string_data(client, mock_httpx_request):
    mock_httpx_request.return_value = httpx.Response(200, request=httpx.Request("POST", "http://testserver"), content=b'{"mock": "response"}')
    req = {"upstream_url": "https://api.github.com/test", "method": "POST", "data": "stringdata"}
    res = client.post("/proxy/upstream", json=req)
    assert res.status_code == 200

def test_proxy_upstream_none_data(client, mock_httpx_request):
    mock_httpx_request.return_value = httpx.Response(200, request=httpx.Request("POST", "http://testserver"), content=b'{"mock": "response"}')
    req = {"upstream_url": "https://api.github.com/test", "method": "POST", "data": None}
    res = client.post("/proxy/upstream", json=req)
    assert res.status_code == 200

def test_proxy_upstream_int_data(client, mock_httpx_request):
    mock_httpx_request.return_value = httpx.Response(200, request=httpx.Request("POST", "http://testserver"), content=b'{"mock": "response"}')
    req = {"upstream_url": "https://api.github.com/test", "method": "POST", "data": 42}
    res = client.post("/proxy/upstream", json=req)
    assert res.status_code == 200

def test_proxy_upstream_json_decode_error(client, mock_httpx_request):
    mock_httpx_request.return_value = httpx.Response(
        200, request=httpx.Request("POST", "http://testserver"), headers={"content-type": "application/json"}, content=b'invalid json'
    )
    req = {"upstream_url": "https://api.github.com/test", "method": "GET"}
    res = client.post("/proxy/upstream", json=req)
    assert res.status_code == 200
    assert res.json()["upstream"]["content_type"] == "application/json"

def test_chat_completions_error(client, mock_litellm_acompletion):
    import uuid
    mock_litellm_acompletion.side_effect = Exception("Error")
    req = {"model": "gpt-4", "messages": [{"role": "user", "content": f"hi {uuid.uuid4()}"}]}
    res = client.post("/v1/chat/completions", json=req)
    assert res.status_code == 500

def test_chat_completions_compression_savings(client, mock_litellm_acompletion):
    class MockResponse:
        def model_dump(self):
            return {"id": "cmpl", "choices": [{"message": {"content": "ok"}}]}
    mock_litellm_acompletion.return_value = MockResponse()
    
    # Mock token optimizer to force savings > 0
    with patch("core.app_config.axon_service._optimizer.optimize") as mock_opt:
        class DummyWinner:
            @property
            def encoded(self): return "compressed!"
            @property
            def savings_vs_json_pct(self): return 50.0
            @property
            def token_estimate(self): return 5
        class DummyResult:
            @property
            def winner(self): return DummyWinner()
            @property
            def json_baseline_tokens(self): return 10
            
        mock_opt.return_value = DummyResult()
        
        req = {"model": "gpt-4", "messages": [{"role": "user", "content": "A" * 100}]}
        res = client.post("/v1/chat/completions", json=req)
        assert res.status_code == 200

@pytest.mark.asyncio
async def test_stream_openai_error():
    from api.routes.v1_openai_routes import _stream_openai
    with patch("litellm.acompletion") as mock_stream:
        mock_stream.side_effect = Exception("Stream timeout")
        
        gen = _stream_openai("http://fake", {}, {})
        with pytest.raises(Exception):
            lines = [line async for line in gen]
