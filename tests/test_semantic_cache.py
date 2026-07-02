from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pytest

from services.semantic_cache import SemanticCache


@pytest.fixture
def cache():
    return SemanticCache()

@pytest.mark.asyncio
async def test_fast_cosine(cache):
    assert cache._fast_cosine([1, 0], 1, [0, 1], 1) == 0.0
    assert cache._fast_cosine([1, 0], 0, [0, 1], 1) == 0.0

@pytest.mark.asyncio
async def test_extract_context_and_question(cache):
    # Empty
    assert cache._extract_context_and_question([]) == ("", "")

    # Last is not user
    msgs = [{"role": "assistant", "content": "hi"}]
    ctx, q = cache._extract_context_and_question(msgs)
    assert q == ""
    assert ctx != ""

@pytest.mark.asyncio
async def test_get_embedding(cache):
    # Empty string
    assert await cache.get_embedding("   ", "key") is None

    # Embedder failure
    with patch("services.intent_classifier.get_embedder", return_value=None):
        assert await cache.get_embedding("test", "key") is None

    # Embedder throws exception
    mock_emb = MagicMock()
    mock_emb.embed.side_effect = Exception("err")
    with patch("services.intent_classifier.get_embedder", return_value=mock_emb):
        assert await cache.get_embedding("test", "key") is None

    # Success
    mock_emb = MagicMock()
    mock_emb.embed.return_value = [MagicMock(tolist=lambda: [0.1, 0.2])]
    with patch("services.intent_classifier.get_embedder", return_value=mock_emb):
        res = await cache.get_embedding("test", "key")
        assert res == [0.1, 0.2]

@pytest.mark.asyncio
async def test_check_cache_edge_cases(cache):
    # Empty messages
    assert await cache.check_cache([], "key") == (None, None)

    # Last not user
    assert await cache.check_cache([{"role": "assistant"}], "key") == (None, None)

    # No embedding
    with patch.object(cache, "get_embedding", return_value=None):
        res, state = await cache.check_cache([{"role": "user", "content": "hi"}], "key")
        assert res is None
        assert state["embedding"] is None

    # No memory store support
    with patch.object(cache, "get_embedding", return_value=[0.1]):
        with patch("services.semantic_cache.memory_store", spec=[]): # No get_active_semantic_cache
            res, state = await cache.check_cache([{"role": "user", "content": "hi"}], "key")
            assert res is None

    # Corrupted row
    mock_store = MagicMock()
    mock_store.get_active_semantic_cache = AsyncMock(return_value=[
        {"embedding": "bad json", "response_json": "{}"}
    ])
    with patch.object(cache, "get_embedding", return_value=[0.1]):
        with patch("services.semantic_cache.memory_store", mock_store):
            res, state = await cache.check_cache([{"role": "user", "content": "hi"}], "key")
            assert res is None

@pytest.mark.asyncio
async def test_store_response_edge_cases(cache):
    # Empty
    await cache.store_response(None, {})
    await cache.store_response({}, None)

    # Missing fields
    await cache.store_response({"context_hash": "123"}, {"a": 1})

@pytest.mark.asyncio
async def test_get_all_entries(cache):
    # No support
    with patch("services.semantic_cache.memory_store", spec=[]):
        assert await cache.get_all_entries() == []

    # Valid support
    mock_store = MagicMock()
    mock_store.get_all_semantic_cache_entries = AsyncMock(return_value=[
        {"created_at": "2023-01-01T00:00:00Z", "context_hash": "a", "question": "q"},
        {"created_at": "bad date", "context_hash": "b", "question": "q2"}
    ])
    with patch("services.semantic_cache.memory_store", mock_store):
        entries = await cache.get_all_entries()
        assert len(entries) == 2
        assert entries[0]["context_hash"] == "a"
        assert entries[1]["context_hash"] == "b"

@pytest.mark.asyncio
async def test_check_cache_success(cache):
    mock_store = MagicMock()
    # Provide a valid row that will score perfectly
    mock_store.get_active_semantic_cache = AsyncMock(return_value=[
        {
            "embedding": orjson.dumps([1.0, 0.0]).decode(),
            "response_json": orjson.dumps({"success": True}).decode()
        }
    ])
    with patch.object(cache, "get_embedding", return_value=[1.0, 0.0]):
        with patch("services.semantic_cache.memory_store", mock_store):
            res, state = await cache.check_cache([{"role": "user", "content": "hi"}], "key")
            assert res == {"success": True}
            assert state["question"] == "hi"

@pytest.mark.asyncio
async def test_store_response_success(cache):
    mock_store = MagicMock()
    mock_store.store_semantic_cache = AsyncMock()
    with patch("services.semantic_cache.memory_store", mock_store):
        await cache.store_response(
            {"context_hash": "abc", "question": "q", "embedding": [0.1]},
            {"response": "ok"}
        )
        mock_store.store_semantic_cache.assert_called_once_with("abc", "q", [0.1], {"response": "ok"})
