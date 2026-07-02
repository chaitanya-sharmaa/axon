"""MCP-style adapter layer using the Axon service for compact tool I/O."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.bridge_service import AxonService
from services.token_optimizer import TokenOptimizer


class AxonMCPAdapter:
    """Adapter helpers for wrapping tool results and decoding model inputs."""

    def __init__(self, axon_service: AxonService | None = None) -> None:
        if axon_service:
            self.bridge = axon_service
        else:
            # If no service is provided, create a default one for standalone use.
            # This requires creating a default TokenOptimizer as well.
            self.bridge = AxonService(token_optimizer=TokenOptimizer(), include_json_fallback=True)

    def decode_model_input(self, inbound: Any) -> Any:
        """Decode inbound JSON/Axon/object to normalized Python object."""
        return self.bridge.from_any_to_object(inbound)

    def encode_tool_output(self, output: Any, session_id: str | None = None) -> dict[str, Any]:
        """Encode tool output with Axon-first envelope for model consumption."""
        return self.bridge.convert_output(output, session_id=session_id)

    def invoke_tool(
        self,
        tool_handler: Callable[[Any], Any],
        inbound: Any,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Normalize input, invoke tool handler, return Axon envelope."""
        normalized = self.decode_model_input(inbound)
        result = tool_handler(normalized)
        return self.encode_tool_output(result, session_id=session_id)
