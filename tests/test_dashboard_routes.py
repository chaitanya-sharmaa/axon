import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_dashboard_route():
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<title>dashboard</title>" in response.text
