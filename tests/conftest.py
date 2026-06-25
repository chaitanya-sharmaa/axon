"""pytest configuration for the Axon bridge test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure bridge/ is in sys.path before we import anything
_BRIDGE_ROOT = Path(__file__).parent.parent.resolve()
if str(_BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_ROOT))

# Set test environment variables BEFORE importing app
os.environ["AXON_MEMORY_TYPE"] = "sqlite"
os.environ["AXON_MEMORY_DB_PATH"] = ":memory:"
os.environ["AXON_REQUIRE_API_KEY"] = "false"
os.environ["AXON_API_KEY"] = "test-key"
os.environ["AXON_ALLOW_ALL_DOMAINS"] = "true"


@pytest.fixture
def client():
    """Returns a TestClient instance for the FastAPI app."""
    # We import app here so the environment variables above take effect first
    from app import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_httpx_post():
    """Mocks httpx.AsyncClient.post."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        yield mock_post


@pytest.fixture
def mock_httpx_request():
    """Mocks httpx.AsyncClient.request."""
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        yield mock_req


@pytest.fixture
def mock_litellm_acompletion():
    """Mocks litellm.acompletion."""
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        yield mock_acompletion


@pytest.fixture
def mock_redis():
    """Mocks redis.asyncio.from_url to prevent actual Redis connections."""
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis_client = AsyncMock()
        mock_from_url.return_value = mock_redis_client
        yield mock_redis_client

@pytest.fixture(autouse=True)
def reset_security_config():
    """Reset security config to default test values before and after each test."""
    from core.app_config import security_config
    
    def reset():
        security_config.allow_all_domains = True
        security_config.require_api_key = False
        security_config.api_key = "test-key"
        security_config.allowed_domains = ["api.github.com", "api.openai.com"]
        
    reset()
    yield
    reset()


