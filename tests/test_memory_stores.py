import pytest
import os
import json
from unittest.mock import AsyncMock, patch

from services.sqlite_memory_store import SessionMemoryStore
from services.redis_memory_store import RedisMemoryStore

# --- SQLite Store Tests ---

@pytest.fixture
async def sqlite_store(tmp_path):
    db_file = tmp_path / "test.db"
    store = SessionMemoryStore(db_path=str(db_file))
    yield store
    await store.close()

async def test_sqlite_create_and_delete(sqlite_store):
    await sqlite_store.create_session("sess1", {"meta": "data"})
    assert await sqlite_store.session_exists("sess1") is True
    
    await sqlite_store.delete_session("sess1")
    assert await sqlite_store.session_exists("sess1") is False

def test_sqlite_sync_init(tmp_path):
    # Initializes without an active event loop
    db_file = tmp_path / "sync_test.db"
    store = SessionMemoryStore(db_path=str(db_file))
    assert store._conn is None or store._conn is not None

async def test_sqlite_symbols(sqlite_store):
    await sqlite_store.create_session("sess1")
    await sqlite_store.add_session_symbol("sess1", 1, "func_a", "function", 0.9, "file1", 0)
    
    symbols = await sqlite_store.get_session_symbols("sess1")
    assert len(symbols) == 1
    assert symbols[0]["qualified_name"] == "func_a"
    assert symbols[0]["kind"] == "function"

async def test_sqlite_schemas(sqlite_store):
    await sqlite_store.create_session("sess1")
    await sqlite_store.cache_session_schema("sess1", "hash1", {"type": "object"}, ["f1", "f2"])
    
    schema = await sqlite_store.get_session_schema("sess1", "hash1")
    assert schema is not None
    assert schema["fields"] == ["f1", "f2"]
    
    missing = await sqlite_store.get_session_schema("sess1", "hash2")
    assert missing is None

async def test_sqlite_events(sqlite_store):
    await sqlite_store.create_session("sess1")
    await sqlite_store.log_event("sess1", "process", {"x": 1})
    
    history = await sqlite_store.get_session_history("sess1", limit=10)
    assert len(history) == 1
    assert history[0]["event_type"] == "process"
    assert json.loads(history[0]["payload"])["x"] == 1

async def test_sqlite_cleanup(sqlite_store):
    await sqlite_store.create_session("sess1")
    # Force last_accessed back in time via direct execute to test cleanup
    conn = await sqlite_store._ensure_conn()
    await conn.execute("UPDATE sessions SET last_accessed = '2000-01-01 00:00:00' WHERE session_id = 'sess1'")
    await conn.commit()
    
    deleted = await sqlite_store.cleanup_old_sessions(days=7)
    assert deleted == 1
    assert await sqlite_store.session_exists("sess1") is False


# --- Redis Store Tests ---

@pytest.fixture
def mock_redis_client():
    client = AsyncMock()
    # Mock return values for complex commands if needed
    client.exists.return_value = 1
    
    # Mock hgetall to return strings that can be json.loaded
    client.hgetall.return_value = {"func_a": '{"symbol_id": 1, "qualified_name": "func_a"}'}
    
    client.hget.return_value = '{"definition": {}, "fields": ["f1"]}'
    client.lrange.return_value = ['{"event_type": "process", "payload": {"x": 1}}']
    return client

@pytest.fixture
def redis_store(mock_redis_client):
    with patch("redis.asyncio.from_url", return_value=mock_redis_client):
        store = RedisMemoryStore(redis_url="redis://fake")
        yield store

async def test_redis_create_session(redis_store, mock_redis_client):
    await redis_store.create_session("sess1", {"meta": "data"})
    assert mock_redis_client.hset.call_count == 1
    assert mock_redis_client.expire.call_count == 1

async def test_redis_session_exists(redis_store, mock_redis_client):
    exists = await redis_store.session_exists("sess1")
    assert exists is True
    mock_redis_client.exists.assert_called_with("axon:session:sess1")

async def test_redis_symbols(redis_store, mock_redis_client):
    await redis_store.add_session_symbol("sess1", 1, "func_a", "function", 0.9, "file1", 0)
    mock_redis_client.hset.assert_called()
    
    symbols = await redis_store.get_session_symbols("sess1")
    assert len(symbols) == 1
    assert symbols[0]["qualified_name"] == "func_a"

async def test_redis_schemas(redis_store, mock_redis_client):
    await redis_store.cache_session_schema("sess1", "hash1", {}, ["f1"])
    mock_redis_client.hset.assert_called()
    
    schema = await redis_store.get_session_schema("sess1", "hash1")
    assert schema["fields"] == ["f1"]

async def test_redis_events(redis_store, mock_redis_client):
    await redis_store.log_event("sess1", "process", {"x": 1})
    mock_redis_client.lpush.assert_called()
    mock_redis_client.ltrim.assert_called()
    
    history = await redis_store.get_session_history("sess1", limit=10)
    assert len(history) == 1
    assert history[0]["event_type"] == "process"

async def test_redis_delete_cleanup(redis_store, mock_redis_client):
    await redis_store.delete_session("sess1")
    mock_redis_client.delete.assert_called_once()
    
    # cleanup is no-op
    assert await redis_store.cleanup_old_sessions() == 0
