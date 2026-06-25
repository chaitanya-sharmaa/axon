import asyncio
from fastapi.testclient import TestClient

import os
os.environ["AXON_MEMORY_TYPE"] = "sqlite"
os.environ["AXON_MEMORY_DB_PATH"] = ":memory:"
os.environ["AXON_REQUIRE_API_KEY"] = "false"

from app import app
from core.app_config import memory_store

print("Starting client...", flush=True)
with TestClient(app) as client:
    print("Client started. Sending request...", flush=True)
    req = {
        "inbound": {"items": [{"id": 1, "status": "active"}]},
        "handler": "active_items",
        "session_id": "test_sess"
    }
    res = client.post("/process", json=req)
    print("Response status:", res.status_code, flush=True)
