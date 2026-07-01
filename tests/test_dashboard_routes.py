import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import os

from api.routes.dashboard_routes import router
from core.settings import settings

app = FastAPI()
app.include_router(router)
client = TestClient(app)

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test_key"}

@pytest.fixture(autouse=True)
def setup_settings():
    old_key = settings.admin_api_key
    settings.admin_api_key = "test_key"
    yield
    settings.admin_api_key = old_key

def test_dashboard_route_exists():
    with patch("os.path.exists", return_value=True):
        with patch("fastapi.responses.FileResponse") as mock_file:
            # We bypass the actual file return for test stability if FileResponse actually reads it
            pass
            
    # When file exists (real app has it)
    response = client.get("/dashboard")
    if response.status_code == 200:
        assert "text/html" in response.headers["content-type"]
    else:
        assert response.status_code == 200

def test_dashboard_route_missing():
    with patch("os.path.exists", return_value=False):
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "error" in response.json()

def test_require_admin():
    # Missing key
    response = client.get("/admin/features")
    assert response.status_code == 403
    
    # Invalid key
    response = client.get("/admin/features", headers={"Authorization": "Bearer wrong_key"})
    assert response.status_code == 403
    
    # Valid key
    response = client.get("/admin/features", headers={"Authorization": "Bearer test_key"})
    assert response.status_code == 200

def test_update_features(auth_headers):
    # Test updating some flags
    payload = {
        "enable_semantic_routing": False,
        "enable_exact_match_cache": False,
        "enable_tool_compression": False,
        "enable_rag_context": False,
        "enable_agentic_optimizations": False,
        "enable_agentic_schema_diff": False,
        "enable_agentic_scratchpad": False,
        "enable_agentic_observation_window": False,
        "enable_agentic_loop_detection": False,
    }
    response = client.post("/admin/features", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    for v in data.values():
        if isinstance(v, bool):
            assert v is False
            
    # Test setting some back to true
    payload = {
        "enable_semantic_routing": True,
        "enable_agentic_optimizations": True
    }
    response = client.post("/admin/features", json=payload, headers=auth_headers)
    data = response.json()
    assert data["enable_semantic_routing"] is True
    assert data["enable_agentic_optimizations"] is True

def test_get_requests(auth_headers):
    with patch("api.routes.dashboard_routes.request_logger") as mock_logger:
        mock_logger.get_logs.return_value = [{"req": 1}]
        response = client.get("/admin/requests", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == [{"req": 1}]

@pytest.mark.asyncio
async def test_get_cache_entries(auth_headers):
    with patch("api.routes.dashboard_routes.semantic_cache") as mock_cache:
        mock_cache.get_all_entries = AsyncMock(return_value=[{"cache": 1}])
        
        # We need async test client or rely on fastapi handling
        # TestClient is sync, so it will execute async endpoints internally
        pass
        
    with patch("api.routes.dashboard_routes.semantic_cache") as mock_cache:
        mock_cache.get_all_entries = AsyncMock(return_value=[{"cache": 1}])
        response = client.get("/admin/cache", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == [{"cache": 1}]

def test_get_events(auth_headers):
    with patch("api.routes.dashboard_routes.event_logger") as mock_events:
        mock_events.get_firewall_events.return_value = [{"fw": 1}]
        response = client.get("/admin/events/firewall", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == [{"fw": 1}]

        mock_events.get_pii_events.return_value = [{"pii": 1}]
        mock_events.pii_type_counts.return_value = {"EMAIL": 1}
        response = client.get("/admin/events/pii", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["events"] == [{"pii": 1}]
        
        mock_events.get_entropy_events.return_value = [{"ent": 1}]
        response = client.get("/admin/events/entropy", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == [{"ent": 1}]

def test_get_health(auth_headers):
    with patch("api.routes.dashboard_routes.request_logger") as mock_logger:
        # 1 valid, 1 error
        import time
        now = time.time()
        mock_logger.get_logs.return_value = [
            {"timestamp": now, "status_code": 200, "cost": 0.01},
            {"timestamp": now - 100, "status_code": 500, "cost": 0.02}
        ]
        response = client.get("/admin/health", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["error_count"] == 1
        assert data["requests_last_minute"] == 1 # only one recent
        assert data["total_cost_usd"] == 0.03

def test_get_tenants_and_sessions(auth_headers):
    with patch("api.routes.dashboard_routes.memory_store") as mock_store:
        mock_store.list_all_tenants = AsyncMock(return_value=[{"tenant": 1}])
        mock_store.list_all_sessions = AsyncMock(return_value=[{"session": 1}])
        
        res_t = client.get("/admin/tenants", headers=auth_headers)
        assert res_t.status_code == 200
        assert res_t.json() == [{"tenant": 1}]
        
        res_s = client.get("/admin/sessions", headers=auth_headers)
        assert res_s.status_code == 200
        assert res_s.json() == [{"session": 1}]

def test_get_tenants_and_sessions_no_support(auth_headers):
    with patch("api.routes.dashboard_routes.memory_store", spec=[]):
        res_t = client.get("/admin/tenants", headers=auth_headers)
        assert res_t.json() == []
        
        res_s = client.get("/admin/sessions", headers=auth_headers)
        assert res_s.json() == []
        
def test_get_tenants_and_sessions_exception(auth_headers):
    with patch("api.routes.dashboard_routes.memory_store") as mock_store:
        mock_store.list_all_tenants = AsyncMock(side_effect=Exception)
        mock_store.list_all_sessions = AsyncMock(side_effect=Exception)
        
        res_t = client.get("/admin/tenants", headers=auth_headers)
        assert res_t.json() == []
        
        res_s = client.get("/admin/sessions", headers=auth_headers)
        assert res_s.json() == []

def test_get_agentic_stats(auth_headers):
    with patch("api.routes.dashboard_routes.request_logger") as mock_logger:
        mock_logger.get_logs.return_value = [
            {"agentic_tokens_saved": 10, "agentic_breakdown": {"a": 5, "b": 5}},
            {"agentic_tokens_saved": 20, "agentic_breakdown": {"a": 20}},
            {"other_key": 1} # no agentic stats
        ]
        with patch("api.routes.dashboard_routes.agentic_state_manager") as mock_manager:
            mock_manager.stats.return_value = {"active_sessions": 2}
            
            response = client.get("/admin/agentic", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["active_sessions"] == 2
            assert data["total_agentic_tokens_saved"] == 30
            assert data["breakdown_totals"]["a"] == 25
            assert data["breakdown_totals"]["b"] == 5
