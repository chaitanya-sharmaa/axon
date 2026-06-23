import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import os

from app import app
from core.settings import settings

client = TestClient(app)

def test_admin_routes_disabled():
    with patch.object(settings, 'admin_api_key', None):
        response = client.get("/admin/tenants/t1")
        assert response.status_code == 403
        assert "disabled" in response.text

def test_admin_routes_invalid_key():
    with patch.object(settings, 'admin_api_key', "secret_key"):
        response = client.get("/admin/tenants/t1", headers={"X-Admin-API-Key": "wrong_key"})
        assert response.status_code == 401
        
        response2 = client.get("/admin/tenants/t1") # No header
        assert response2.status_code == 401

def test_admin_routes_get_tenant():
    with patch.object(settings, 'admin_api_key', "secret_key"):
        response = client.get("/admin/tenants/t1", headers={"X-Admin-API-Key": "secret_key"})
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == "t1"
        assert "monthly_quota_usd" in data

def test_admin_routes_set_tenant():
    with patch.object(settings, 'admin_api_key', "secret_key"):
        response = client.post(
            "/admin/tenants/t1", 
            headers={"X-Admin-API-Key": "secret_key"},
            json={"monthly_quota_usd": 15.0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["monthly_quota_usd"] == 15.0
        
        # Test negative quota
        response2 = client.post(
            "/admin/tenants/t1", 
            headers={"X-Admin-API-Key": "secret_key"},
            json={"monthly_quota_usd": -5.0}
        )
        assert response2.status_code == 400
        assert "negative" in response2.text
