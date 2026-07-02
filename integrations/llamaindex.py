import json

from pydantic import ConfigDict, Field

try:
    from llama_index.core.postprocessor.types import BaseNodePostprocessor
    from llama_index.core.schema import NodeWithScore, QueryBundle
except ImportError:
    raise ImportError("Please install llama-index-core to use the AxonNodePostprocessor: pip install llama-index-core")

from services.text_pruner import prune_text
from services.token_optimizer import TokenOptimizer


class AxonNodePostprocessor(BaseNodePostprocessor):
    """
    A LlamaIndex NodePostprocessor that automatically prunes and compresses 
    the text of retrieved chunks using Axon's TokenOptimizer.
    
    It intercepts retrieved context nodes (RAG chunks) and compresses them 
    before they are injected into the final LLM prompt.
    """
    optimizer: TokenOptimizer = Field(description="The Axon TokenOptimizer instance")
    session_id: str | None = Field(default=None, description="Optional session ID for tracking")
    model: str = Field(default="gpt-4o", description="The target LLM model for accurate tokenization")
    enable_pruning: bool = Field(default=True, description="Whether to apply semantic pruning before compression")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: QueryBundle | None = None,
    ) -> list[NodeWithScore]:

        for node_with_score in nodes:
            original_text = node_with_score.node.text
            if not original_text or len(original_text) < 50:
                continue

            # 1. Semantic Pruning (Stop-words & Whitespace)
            working_text = original_text
            if self.enable_pruning and len(working_text) > 500:
                working_text = prune_text(working_text)

            # 2. Structural Token Optimization
            result = self.optimizer.optimize(
                {"text": working_text},
                session_id=self.session_id,
                model=self.model
            )

            # 3. Update Node Text
            if result.winner.savings_vs_json_pct > 0:
                # If it compressed effectively, substitute the text
                if isinstance(result.winner.encoded, str):
                    node_with_score.node.text = result.winner.encoded
                else:
                    node_with_score.node.text = json.dumps(result.winner.encoded)
            elif self.enable_pruning:
                node_with_score.node.text = working_text

            # 4. Attach Observability Metrics to Node Metadata
            saved = max(0, result.json_baseline_tokens - result.winner.token_estimate)
            node_with_score.node.metadata["axon_original_tokens"] = result.json_baseline_tokens
            node_with_score.node.metadata["axon_compressed_tokens"] = result.winner.token_estimate
            node_with_score.node.metadata["axon_tokens_saved"] = saved
            node_with_score.node.metadata["axon_strategy"] = result.winner.strategy

        return nodes
