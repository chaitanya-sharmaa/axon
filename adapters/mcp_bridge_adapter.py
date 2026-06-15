"""MCP-style adapter layer using the Axon service for compact tool I/O."""

from __future__ import annotations

from typing import Any, Callable

from services.bridge_service import AxonService


class AxonMCPAdapter:
    """Adapter helpers for wrapping tool results and decoding model inputs."""

    def __init__(self, axon_service: AxonService | None = None) -> None:
        self.bridge = axon_service or AxonService(include_json_fallback=True)

    def decode_model_input(self, inbound: Any) -> Any:
        """Decode inbound JSON/GCF/object to normalized Python object."""
        return self.bridge.from_any_to_object(inbound)

    def encode_tool_output(self, output: Any, session_id: str | None = None) -> dict[str, Any]:
        """Encode tool output with GCF-first envelope for model consumption."""
        return self.bridge.convert_output(output, session_id=session_id)

    def invoke_tool(
        self,
        tool_handler: Callable[[Any], Any],
        inbound: Any,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Normalize input, invoke tool handler, return GCF envelope."""
        normalized = self.decode_model_input(inbound)
        result = tool_handler(normalized)
        return self.encode_tool_output(result, session_id=session_id)
