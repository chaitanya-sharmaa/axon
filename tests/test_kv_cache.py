import pytest
import asyncio
from services.kv_cache import ExactMatchCache

@pytest.fixture
def cache():
    return ExactMatchCache(maxsize=2, ttl_seconds=60)

def test_deterministic_hash(cache):
    req1 = {"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}], "temperature": 0.5}
    # Same keys, different insertion order
    req2 = {"temperature": 0.5, "model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}
    
    hash1 = cache._compute_hash(req1)
    hash2 = cache._compute_hash(req2)
    
    assert hash1 == hash2

@pytest.mark.asyncio
async def test_set_and_get(cache):
    req = {"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]}
    resp = {"choices": [{"message": {"content": "world"}}]}
    
    # Initially None
    assert await cache.get(req) is None
    
    # Set and retrieve
    await cache.set(req, resp)
    cached = await cache.get(req)
    
    assert cached == resp

@pytest.mark.asyncio
async def test_eviction(cache):
    # Max size is 2
    req1 = {"id": 1}
    req2 = {"id": 2}
    req3 = {"id": 3}
    
    await cache.set(req1, {"res": 1})
    await cache.set(req2, {"res": 2})
    await cache.set(req3, {"res": 3})
    
    # At least one should be evicted
    assert len(cache._cache) == 2
    # Since dict insertion order pops oldest, req1 should be gone
    assert await cache.get(req1) is None
    assert await cache.get(req2) == {"res": 2}
    assert await cache.get(req3) == {"res": 3}

@pytest.mark.asyncio
async def test_ttl(cache):
    cache.ttl_seconds = 0.01  # extremely short TTL
    req = {"id": 1}
    
    await cache.set(req, {"res": 1})
    await asyncio.sleep(0.02)
    
    # Should be expired
    assert await cache.get(req) is None
