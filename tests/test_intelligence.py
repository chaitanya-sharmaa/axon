import pytest
from unittest.mock import patch, AsyncMock
import os

from services.token_optimizer import TokenOptimizer, _build_payload
from services.smart_router import route_model, fallback_model
from services.semantic_cache import SemanticCache

def test_smart_router():
    with patch.dict(os.environ, {"AXON_AUTO_ROUTING": "true"}):
        # Should route simple payloads to a smaller model
        assert route_model("gpt-4o", 500) == "gpt-4o-mini"
        assert route_model("gpt-4o", 2000) == "gpt-4o"
        
        # Check fallback logic
        assert fallback_model("gpt-4o") == "gpt-4-turbo"
        assert fallback_model("unknown-model") == "unknown-model"

@pytest.mark.asyncio
async def test_semantic_cache():
    cache = SemanticCache(threshold=0.90)
    
    with patch.object(cache, 'get_embedding', new_callable=AsyncMock) as mock_get_embedding:
        # Mocking an embedding representing "hello"
        mock_get_embedding.return_value = [1.0, 0.0]
        
        # Test empty cache miss
        cached, emb = await cache.check_cache("hello world", "fake_key")
        assert cached is None
        assert emb == [1.0, 0.0]
        
        # Store response
        cache.store_response("hello world", emb, {"choices": [{"message": {"content": "hi"}}]})
        
        # Test cache hit with same embedding
        cached2, emb2 = await cache.check_cache("hello world!", "fake_key")
        assert cached2 is not None
        assert cached2["choices"][0]["message"]["content"] == "hi"

def test_auto_tuning():
    optimizer = TokenOptimizer()
    session_id = "test-session-tuning"
    payload = {"key": "val1"} # generic
    
    # 3 generic calls should trigger auto-tuning
    for _ in range(3):
        optimizer.optimize(payload, session_id=session_id)
        
    # Check history
    history = optimizer._strategy_wins.get(session_id, {})
    assert "generic" in history and history["generic"][0] == "schema_values" and history["generic"][1] >= 3
    
    # Fourth call should fast-path
    res = optimizer.optimize(payload, session_id=session_id)
    assert res.winner.strategy == "schema_values"
    
def test_context_pruning():
    # Construct a massive graph payload
    payload = {
        "query": "find auth_user",
        "symbols": [
            {"qualified_name": "auth_user", "score": 1.0},
            {"qualified_name": "database_conn", "score": 1.0},
        ] + [{"qualified_name": f"junk_symbol_{i}", "score": 0.1} for i in range(100)]
    }
    
    built = _build_payload(payload)
    
    # We gave 102 symbols. Pruning (bottom 25%) should leave max 102 * 0.75 = 76 symbols.
    assert built is not None
    assert len(built.symbols) <= 76
    
    # auth_user should survive because it matches query perfectly
    names = [s.qualified_name for s in built.symbols]
    assert "auth_user" in names
