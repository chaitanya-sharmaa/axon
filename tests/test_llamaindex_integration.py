import pytest
import json
from unittest.mock import MagicMock

try:
    from llama_index.core.schema import NodeWithScore, TextNode
    from integrations.llamaindex import AxonNodePostprocessor
except ImportError:
    pytest.skip("llama-index-core not installed", allow_module_level=True)

from services.token_optimizer import TokenOptimizer, OptimizerResult

class DummyWinner:
    def __init__(self, token_estimate, encoded, strategy, savings_vs_json_pct):
        self.token_estimate = token_estimate
        self.encoded = encoded
        self.strategy = strategy
        self.savings_vs_json_pct = savings_vs_json_pct

def test_axon_node_postprocessor():
    mock_optimizer = MagicMock(spec=TokenOptimizer)
    
    node1 = NodeWithScore(node=TextNode(text="This is a very long text that should be compressed " * 20), score=0.9)
    node2 = NodeWithScore(node=TextNode(text="Short text"), score=0.8)
    
    def mock_optimize(payload, session_id=None, model="gpt-4o"):
        text_len = len(payload["text"])
        if text_len > 50:
            winner = DummyWinner(
                token_estimate=10, 
                encoded="Compressed generic format", 
                strategy="generic", 
                savings_vs_json_pct=50.0
            )
            return OptimizerResult(winner=winner, all_results=[], json_baseline_tokens=20, payload_type="text")
        else:
            winner = DummyWinner(
                token_estimate=5, 
                encoded=payload["text"], 
                strategy="json", 
                savings_vs_json_pct=0.0
            )
            return OptimizerResult(winner=winner, all_results=[], json_baseline_tokens=5, payload_type="text")

    mock_optimizer.optimize.side_effect = mock_optimize

    postprocessor = AxonNodePostprocessor(optimizer=mock_optimizer, enable_pruning=False)
    
    processed_nodes = postprocessor.postprocess_nodes([node1, node2])
    
    assert len(processed_nodes) == 2
    
    # Node 1 should be compressed
    assert processed_nodes[0].node.text == "Compressed generic format"
    assert processed_nodes[0].node.metadata["axon_strategy"] == "generic"
    assert processed_nodes[0].node.metadata["axon_tokens_saved"] == 10
    
    # Node 2 should be untouched
    assert processed_nodes[1].node.text == "Short text"
    assert "axon_strategy" not in processed_nodes[1].node.metadata
