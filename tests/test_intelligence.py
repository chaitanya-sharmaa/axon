import os
from unittest.mock import AsyncMock, patch

import pytest

from services.semantic_cache import SemanticCache
from services.smart_router import fallback_model, route_model
from services.token_optimizer import TokenOptimizer, _build_payload


def test_smart_router():
    with patch.dict(os.environ, {"AXON_AUTO_ROUTING": "true"}):
        # Should route simple payloads to a smaller model
        assert route_model("gpt-4o", 500, "hello") == "gpt-4o-mini"
        # Should route complex payloads to the pro model
        assert route_model("gpt-4o-mini", 2000, "think step by step to solve this") == "gpt-4o"

        # Check fallback logic
        assert fallback_model("gpt-4o") == "gpt-4-turbo"
        assert fallback_model("unknown-model") == "unknown-model"

@pytest.mark.asyncio
async def test_semantic_cache():
    cache = SemanticCache(threshold=0.90)

    with patch.object(cache, 'get_embedding', new_callable=AsyncMock) as mock_get_embedding:
        import random
        import uuid
        test_str = f"hello world {uuid.uuid4()}"
        # Use high dimensional centered random vector so cos(theta) with other random vectors is ~0
        unique_emb = [random.uniform(-1, 1) for _ in range(128)]
        unique_key = f"fake_key_{uuid.uuid4()}"

        # Mocking an embedding representing our unique string
        mock_get_embedding.return_value = unique_emb

        # Test empty cache miss
        cached, state = await cache.check_cache([{"role": "user", "content": test_str}], unique_key)
        assert cached is None
        assert state["embedding"] == unique_emb

        # Store response
        await cache.store_response(state, {"choices": [{"message": {"content": "hi"}}]})

        # Test cache hit with same embedding
        cached2, state2 = await cache.check_cache([{"role": "user", "content": test_str + "!"}], unique_key)
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

@pytest.mark.asyncio
async def test_fact_extraction():
    from services.fact_extractor import extract_facts_async

    class DummyMemoryStore:
        def __init__(self):
            self.facts = []
        async def create_session(self, session_id):
            pass
        async def add_session_fact(self, session_id, fact):
            self.facts.append(fact)

    store = DummyMemoryStore()

    # Mock httpx.AsyncClient.post
    from unittest.mock import MagicMock
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Mock successful fact extraction
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"facts": ["user=alice", "lang=python"]}'}}]
        }
        mock_post.return_value = mock_response

        await extract_facts_async("test_session", "I am alice and I code in Python.", "api_key", store)

        assert len(store.facts) == 2
        assert "user=alice" in store.facts
        assert "lang=python" in store.facts
