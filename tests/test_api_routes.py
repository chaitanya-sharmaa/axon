from unittest.mock import AsyncMock, patch

import pytest

# --- Core Routes Tests ---

def test_health_live(client):
    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

def test_health_legacy(client):
    res = client.get("/health")
    assert res.status_code == 200

def test_health_ready_success(client):
    with patch("core.app_config.memory_store.session_exists", new_callable=AsyncMock) as mock_exists:
        mock_exists.return_value = False
        res = client.get("/health/ready")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

def test_health_ready_failure(client):
    with patch("core.app_config.memory_store.session_exists", new_callable=AsyncMock) as mock_exists:
        mock_exists.side_effect = Exception("DB down")
        res = client.get("/health/ready")
        assert res.status_code == 503
        assert "Memory store unavailable" in res.json()["detail"]

def test_translate_in(client):
    res = client.post("/translate/in", json={"a": 1})
    assert res.status_code == 200
    assert res.json()["object"] == {"a": 1}

def test_translate_out(client):
    res = client.post("/translate/out", json={"data": {"a": 1}})
    assert res.status_code == 200
    data = res.json()
    assert "compact_text" in data
    assert "metrics" in data

# --- Process Routes Tests ---

def test_process_success(client):
    req = {
        "inbound": {"items": [{"id": 1, "status": "active"}]},
        "handler": "active_items",
        "session_id": "test_sess"
    }
    res = client.post("/process", json=req)
    assert res.status_code == 200
    data = res.json()
    assert "handler_result" in data
    assert data["handler_result"]["summary"]["active"] == 1
    assert data["session_id"] == "test_sess"

def test_process_invalid_handler(client):
    req = {"inbound": {}, "handler": "missing"}
    res = client.post("/process", json=req)
    assert res.status_code == 400
    assert "Unsupported handler" in res.json()["detail"]

# --- Batch Routes Tests ---

def test_batch_process(client):
    req = {
        "requests": [
            {"payload": {"a": 1}, "session_id": "s1"},
            {"payload": {"b": 2}, "session_id": "s2"}
        ]
    }
    res = client.post("/batch", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["batch_size"] == 2
    assert len(data["results"]) == 2

def test_batch_process_too_large(client):
    req = {
        "requests": [{"payload": "a"}] * 101
    }
    res = client.post("/batch", json=req)
    assert res.status_code == 400
    assert "Batch size" in res.json()["detail"]

# --- Agent Routes Tests ---

def test_list_agents(client):
    res = client.get("/agent/list")
    assert res.status_code == 200
    assert len(res.json()["agents"]) > 0 # At least built-ins

def test_agent_dispatch(client):
    req = {"payload": "test", "agent_name": "echo_agent"}
    res = client.post("/agent/dispatch", json=req)
    assert res.status_code == 200
    assert res.json()["success"] is True

def test_agent_swarm(client):
    req = {"payload": "test"}
    res = client.post("/agent/swarm", json=req)
    assert res.status_code == 200
    assert len(res.json()["results"]) > 0

def test_agent_dispatch_parallel(client):
    req = {"payload": "test", "capabilities": ["echo", "graph"]}
    res = client.post("/agent/parallel", json=req)
    assert res.status_code == 200
    assert len(res.json()["results"]) == 2

# --- Memory Routes Tests ---

def test_get_session(client):
    # First create via process
    client.post("/process", json={"inbound": {}, "handler": "echo", "session_id": "mem_sess"})
    res = client.get("/memory/session/mem_sess")
    assert res.status_code == 200
    assert "recent_events" in res.json()

def test_get_session_missing(client):
    res = client.get("/memory/session/missing_sess")
    assert res.status_code == 404

def test_get_session_symbols(client):
    # create session first
    client.post("/process", json={"inbound": {}, "handler": "echo", "session_id": "mem_sess"})
    # wait, there's no route /symbols on memory_routes.py! The route only has /session/{session_id}. Wait, /memory/session/{session_id} returns symbols.
    # Let me check if /memory/session/{session_id}/symbols exists... no it doesn't!
    # Ah, I see from my view_file that the route /session/{session_id} returns them inside the response! So no need to test /symbols.
    pass

def test_cleanup_sessions(client):
    res = client.delete("/memory/cleanup", params={"days": 7})
    assert res.status_code == 200
    assert "deleted_sessions" in res.json()

def test_delete_session(client):
    client.post("/process", json={"inbound": {}, "handler": "echo", "session_id": "del_sess"})
    res = client.delete("/memory/session/del_sess")
    assert res.status_code == 200
    assert res.json()["status"] == "cleared"

def test_delete_session_missing(client):
    # wait, the route doesn't check if session exists before deleting, it just deletes
    # So it should be 200
    res = client.delete("/memory/session/missing_sess")
    assert res.status_code == 200

# --- Security Routes Tests ---

def test_get_security_config(client):
    res = client.get("/security/config")
    assert res.status_code == 200
    assert "allowed_domains" in res.json()

def test_add_domain(client):
    res = client.post("/security/domain/allow", params={"domain": "test-add.com"})
    assert res.status_code == 200
    assert res.json()["action"] == "added"

    # Check it was added
    res2 = client.get("/security/config")
    assert "test-add.com" in res2.json()["allowed_domains"]

def test_remove_domain(client):
    client.post("/security/domain/allow", params={"domain": "test-rem.com"})
    res = client.delete("/security/domain", params={"domain": "test-rem.com"})
    assert res.status_code == 200
    assert res.json()["action"] == "removed"

def test_set_api_key_req(client):
    res = client.post("/security/require-api-key", params={"required": True})
    assert res.status_code == 200
    assert res.json()["require_api_key"] is True

def test_set_allow_all_domains(client):
    res = client.post("/security/allow-all-domains", params={"allow": False})
    assert res.status_code == 200
    assert res.json()["allow_all_domains"] is False

def test_openapi_schema(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    # Call again to hit the cached branch (app.openapi_schema)
    res2 = client.get("/openapi.json")
    assert res2.status_code == 200

def test_openapi_schema_with_logo(client):
    from app import app
    from core.settings import settings as app_settings
    old_logo = app_settings.openapi_logo_url
    object.__setattr__(app_settings, "openapi_logo_url", "http://logo.png")
    app.openapi_schema = None # clear cache
    res = client.get("/openapi.json")
    assert res.status_code == 200
    assert "x-logo" in res.json()["info"]
    object.__setattr__(app_settings, "openapi_logo_url", old_logo)

@pytest.mark.asyncio
async def test_app_lifecycle():
    from app import app
    for handler in app.router.on_startup:
        await handler()
    for handler in app.router.on_shutdown:
        await handler()

def test_list_sessions(client):
    res = client.get("/memory/sessions")
    assert res.status_code == 200
    assert "sessions" in res.json()

def test_batch_process_exception(client):
    with patch("core.app_config.axon_service.convert_output", side_effect=Exception("boom")):
        req = {"requests": [{"payload": "a"}]}
        res = client.post("/batch", json=req)
        assert res.status_code == 200
        assert "boom" in res.json()["results"][0]["error"]

def test_agent_dispatch_fail(client):
    req = {"payload": "test", "capability": "missing_cap"}
    res = client.post("/agent/dispatch", json=req)
    assert res.status_code == 400

def test_agent_dispatch_session(client):
    req = {"payload": "test", "agent_name": "echo_agent", "session_id": "s1"}
    res = client.post("/agent/dispatch", json=req)
    assert res.status_code == 200
    assert res.json()["agent"] == "echo_agent"

def test_agent_swarm_session(client):
    req = {"payload": "test", "session_id": "s2"}
    res = client.post("/agent/swarm", json=req)
    assert res.status_code == 200

def test_agent_parallel_session(client):
    req = {"payload": "test", "capabilities": ["echo"], "session_id": "s3"}
    res = client.post("/agent/parallel", json=req)
    assert res.status_code == 200

def test_agent_parallel_empty_capabilities(client):
    req = {"payload": "test", "capabilities": []}
    res = client.post("/agent/parallel", json=req)
    assert res.status_code == 400
