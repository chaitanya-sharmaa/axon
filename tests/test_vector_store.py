from unittest.mock import MagicMock, patch

import pytest
import torch

from services.vector_store import VectorStore


@pytest.fixture
def store():
    return VectorStore()

def test_chunk_text(store):
    text = "word1 word2 word3 word4"
    # Chunk size 11 will fit "word1 word2" (11 chars)
    chunks = store.chunk_text(text, chunk_size=11)
    assert chunks == ["word1 word2", "word3 word4"]

    # Empty text
    assert store.chunk_text("") == []

@patch("services.vector_store.get_embedder")
def test_add_file_no_embedder(mock_get_embedder, store):
    mock_get_embedder.return_value = None
    store.add_file("file1", "some text")
    assert "file1" in store.files
    assert store.files["file1"]["chunks"] == ["some text"]
    assert store.files["file1"]["embeddings"] is None

@patch("services.vector_store.get_embedder")
def test_add_file_empty_text(mock_get_embedder, store):
    mock_embedder = MagicMock()
    mock_get_embedder.return_value = mock_embedder
    store.add_file("file1", "")
    assert store.files["file1"]["chunks"] == []
    assert store.files["file1"]["embeddings"] is None
    mock_embedder.encode.assert_not_called()

@patch("services.vector_store.get_embedder")
def test_add_file_success(mock_get_embedder, store):
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[0.1, 0.2]]
    mock_get_embedder.return_value = mock_embedder

    store.add_file("file1", "hello")
    assert store.files["file1"]["chunks"] == ["hello"]
    assert torch.is_tensor(store.files["file1"]["embeddings"])
    mock_embedder.encode.assert_called_once_with(["hello"])

@patch("services.vector_store.get_embedder")
def test_search_no_embedder_or_query(mock_get_embedder, store):
    mock_get_embedder.return_value = None
    assert store.search(["file1"], "query") == []

    mock_get_embedder.return_value = MagicMock()
    assert store.search(["file1"], "   ") == []

@patch("services.vector_store.get_embedder")
def test_search_empty_store(mock_get_embedder, store):
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [[1.0, 0.0]]
    mock_get_embedder.return_value = mock_embedder

    assert store.search(["file1"], "query") == []

    # Add a file with no embeddings
    store.files["file2"] = {"chunks": ["chunk1"], "embeddings": None}
    assert store.search(["file2"], "query") == []

@patch("services.vector_store.get_embedder")
def test_search_success(mock_get_embedder, store):
    mock_embedder = MagicMock()

    # Let's say we have 2 chunks.
    # query = [1.0, 0.0]
    # chunk1 = [1.0, 0.0] (score 1.0)
    # chunk2 = [0.0, 1.0] (score 0.0)

    def mock_encode(text):
        if text == "query":
            return [1.0, 0.0]
        elif text == ["chunk1", "chunk2"]:
            return [[1.0, 0.0], [0.0, 1.0]]
        return [0.0, 0.0]

    mock_embedder.encode.side_effect = mock_encode
    mock_get_embedder.return_value = mock_embedder

    store.files["file1"] = {
        "chunks": ["chunk1", "chunk2"],
        "embeddings": torch.tensor([[1.0, 0.0], [0.0, 1.0]])
    }

    results = store.search(["file1"], "query", top_k=2)
    assert len(results) == 1  # Only chunk1 should pass the > 0.2 threshold
    assert results[0] == "chunk1"
