import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock llama_index completely so we can test the file without it installed
mock_llama_index = MagicMock()
from pydantic import BaseModel

mock_base_postprocessor = type("BaseNodePostprocessor", (BaseModel,), {})
mock_schema = MagicMock()
mock_node_with_score = MagicMock
mock_text_node = MagicMock

sys.modules["llama_index"] = mock_llama_index
sys.modules["llama_index.core"] = MagicMock()
sys.modules["llama_index.core.postprocessor"] = MagicMock()
sys.modules["llama_index.core.postprocessor.types"] = MagicMock(BaseNodePostprocessor=mock_base_postprocessor)
sys.modules["llama_index.core.schema"] = MagicMock(NodeWithScore=mock_node_with_score, TextNode=mock_text_node)

from llama_index.core.schema import NodeWithScore, TextNode

from integrations.llamaindex import AxonNodePostprocessor
from services.token_optimizer import TokenOptimizer


def test_llamaindex_postprocessor():
    mock_opt = TokenOptimizer()
    mock_opt.optimize = MagicMock()

    # Setup mock optimization result that compresses well
    mock_res = MagicMock()
    mock_res.json_baseline_tokens = 100
    mock_res.winner.token_estimate = 50
    mock_res.winner.savings_vs_json_pct = 50.0
    mock_res.winner.encoded = "compressed text"
    mock_res.winner.strategy = "yaml"
    mock_opt.optimize.return_value = mock_res

    postprocessor = AxonNodePostprocessor(optimizer=mock_opt)

    # 1. Test short text (should be skipped)
    node1 = NodeWithScore(node=TextNode(text="short", metadata={}))
    nodes = postprocessor._postprocess_nodes([node1])
    assert nodes[0].node.text == "short"
    assert "axon_original_tokens" not in nodes[0].node.metadata

    # 2. Test long text with successful compression (string)
    node2 = NodeWithScore(node=TextNode(text="long text " * 50, metadata={}))
    nodes = postprocessor._postprocess_nodes([node2])
    assert nodes[0].node.text == "compressed text"
    assert nodes[0].node.metadata["axon_original_tokens"] == 100
    assert nodes[0].node.metadata["axon_tokens_saved"] == 50
    assert nodes[0].node.metadata["axon_strategy"] == "yaml"

    # 3. Test long text with successful compression (dict/json)
    mock_res.winner.encoded = {"compressed": "dict"}
    node3 = NodeWithScore(node=TextNode(text="long dict " * 50, metadata={}))
    nodes = postprocessor._postprocess_nodes([node3])
    assert nodes[0].node.text == json.dumps({"compressed": "dict"})

    # 4. Test long text with no savings but pruning enabled
    mock_res.winner.savings_vs_json_pct = 0.0
    mock_res.json_baseline_tokens = 100
    mock_res.winner.token_estimate = 100
    postprocessor = AxonNodePostprocessor(optimizer=mock_opt, enable_pruning=True)

    node4 = NodeWithScore(node=TextNode(text="long text pruning " * 100, metadata={}))
    nodes = postprocessor._postprocess_nodes([node4])
    # The text should be pruned. "long text pruning" x100 is > 500 chars, prune_text removes some spaces.
    # We just ensure it didn't use the 'encoded' mock since savings=0.
    assert "long text pruning" in nodes[0].node.text
    assert nodes[0].node.metadata["axon_tokens_saved"] == 0

def test_llamaindex_import_error():
    # Remove llama_index from sys.modules and mock the import error
    with patch.dict('sys.modules', {'llama_index.core.postprocessor.types': None}):
        with pytest.raises(ImportError):
            import importlib

            import integrations.llamaindex
            importlib.reload(integrations.llamaindex)
