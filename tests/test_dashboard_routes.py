import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_dashboard_route():
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Axon Bridge Dashboard" in response.text
    assert "Tokens Saved" in response.text
