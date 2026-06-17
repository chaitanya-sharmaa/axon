"""Axon service: a token-efficient bridge that converts payloads to a compact format.

Use this between clients and any API/agent to normalize incoming payloads,
convert responses to GCF, and optionally keep JSON alongside for compatibility.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import inspect
import json
from typing import Any, Awaitable, Callable, Dict, Mapping
import tiktoken

from gcf import (
    Edge,
    Payload,
    Session,
    Symbol,
    decode_generic,
    decode,
    encode,
    encode_generic,
    encode_with_session,
)
from core.settings import settings
from services.token_optimizer import TokenOptimizer


class AxonService:
    """Core service for converting payloads to and from compact, token-efficient formats."""

    def __init__(
        self, token_optimizer: TokenOptimizer, include_json_fallback: bool = True
    ) -> None:
        self.include_json_fallback = include_json_fallback
        # Use the optimizer as the single source of truth for session state
        self._optimizer = token_optimizer
        self._tokenizer = tiktoken.get_encoding(settings.tokenizer_model)

    def _estimate_tokens(self, text: str, model: str | None = None) -> int:
        """Estimate tokens. Falls back to optimizer logic if no specific model requested."""
        if model and "gpt" in model:
            return len(self._tokenizer.encode(text))
        return self._optimizer.estimate_tokens_custom(text, model)

    @staticmethod
    def _is_compact_format_text(value: str) -> bool:
        return value.lstrip().startswith("GCF profile=")

    @staticmethod
    def _get_profile(value: str) -> str | None:
        stripped = value.lstrip()
        if not stripped.startswith("GCF profile="):
            return None
        first_line = stripped.splitlines()[0]
        parts = first_line.split()
        for part in parts:
            if part.startswith("profile="):
                return part.split("=", 1)[1]
        return None

    def _normalize_object(self, value: Any) -> Any:
        if is_dataclass(value):
            return self._normalize_object(asdict(value))

        if hasattr(value, "model_dump") and callable(value.model_dump):
            return self._normalize_object(value.model_dump())

        if hasattr(value, "dict") and callable(value.dict):
            return self._normalize_object(value.dict())

        if isinstance(value, Mapping):
            return {str(k): self._normalize_object(v) for k, v in value.items()}

        if isinstance(value, (list, tuple, set)):
            return [self._normalize_object(v) for v in value]

        if isinstance(value, (str, int, float, bool)) or value is None:
            return value

        if hasattr(value, "__dict__"):
            return self._normalize_object(vars(value))

        return str(value)

    def from_any_to_object(self, value: Any) -> Any:
        """Accept JSON/GCF/object input and return a Python object."""
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return ""
            if self._is_compact_format_text(stripped):
                profile = self._get_profile(stripped)
                if profile == "graph":
                    return self._normalize_object(decode(stripped))
                return decode_generic(stripped)
            try:
                parsed = json.loads(stripped)
                return self._normalize_object(parsed)
            except json.JSONDecodeError:
                return {"_text": value}

        return self._normalize_object(value)

    def _to_graph_payload(self, obj: Any) -> Payload | None:
        """Convert to GCF Payload, accepting both strict and flexible formats."""
        if not isinstance(obj, Mapping):
            return None
        symbols_raw = obj.get("symbols")
        if not isinstance(symbols_raw, list):
            return None

        symbols: list[Symbol] = []
        for item in symbols_raw:
            if not isinstance(item, Mapping):
                return None
            
            # Support both strict format (qualified_name) and flexible format (name + module)
            qualified_name = item.get("qualified_name")
            if not qualified_name:
                # Fallback: combine module + name
                name = item.get("name", "unknown")
                module = item.get("module", "")
                qualified_name = f"{module}:{name}" if module else name
            
            if not isinstance(qualified_name, str) or not qualified_name:
                return None
            
            symbols.append(
                Symbol(
                    qualified_name=qualified_name,
                    kind=str(item.get("kind", item.get("type", "function"))),
                    score=float(item.get("score", 1.0)),
                    provenance=str(item.get("provenance", "bridge")),
                    distance=int(item.get("distance", 0)),
                )
            )

        edges: list[Edge] = []
        edges_raw = obj.get("edges", [])
        if isinstance(edges_raw, list):
            for item in edges_raw:
                if not isinstance(item, Mapping):
                    return None
                # Support both strict format (source/target) and flexible format (from/to)
                source = item.get("source") or item.get("from")
                target = item.get("target") or item.get("to")
                if not isinstance(source, str) or not isinstance(target, str):
                    return None
                edges.append(
                    Edge(
                        source=source,
                        target=target,
                        edge_type=str(item.get("edge_type", item.get("type", "references"))),
                        status=item.get("status"),
                    )
                )

        return Payload(
            tool=str(obj.get("tool", "bridge")),
            token_budget=int(obj.get("token_budget", 0)),
            tokens_used=int(obj.get("tokens_used", 0)),
            pack_root=obj.get("pack_root"),
            symbols=symbols,
            edges=edges,
        )

    def _get_session(self, session_id: str) -> Session:
        """Delegates to the TokenOptimizer to get the shared gcf.Session object."""
        return self._optimizer.get_gcf_session(session_id)

    def clear_session(self, session_id: str) -> None:
        """Delegates to the TokenOptimizer to clear the shared session state."""
        self._optimizer.clear_session(session_id)


    def to_compact_text(self, value: Any, session_id: str | None = None) -> str:
        """Convert arbitrary input into a compact text format (graph when possible, else generic)."""
        if isinstance(value, str) and self._is_compact_format_text(value):
            return value
        obj = self.from_any_to_object(value)
        payload = self._to_graph_payload(obj)
        if payload is not None:
            if session_id:
                return encode_with_session(payload, self._get_session(session_id))
            return encode(payload)
        return encode_generic(obj)

    def from_compact_text(self, compact_text: str) -> Any:
        """Decode compact generic profile text back to object form."""
        return decode_generic(compact_text)

    def convert_output(self, value: Any, session_id: str | None = None, model: str | None = None) -> Dict[str, Any]:
        """Convert output to a wire envelope with compact format and token stats."""
        obj = self.from_any_to_object(value)
        json_text = json.dumps(obj, separators=(",", ":"), ensure_ascii=True)
        compact_text = self.to_compact_text(obj, session_id=session_id)

        profile = self._get_profile(compact_text) or "generic"

        json_tokens = self._estimate_tokens(json_text, model=model)
        compact_tokens = self._estimate_tokens(compact_text, model=model)
        savings_pct = round((1 - (compact_tokens / json_tokens)) * 100, 2) if json_tokens else 0.0

        envelope: Dict[str, Any] = {
            "compact_text": compact_text,
            "profile": profile,
            "metrics": {
                "estimated_json_tokens": json_tokens,
                "estimated_compact_tokens": compact_tokens,
                "estimated_savings_percent": savings_pct,
            },
        }
        if session_id:
            envelope["session_id"] = session_id
        if self.include_json_fallback:
            envelope["json"] = obj
        return envelope

    def process(
        self,
        inbound: Any,
        handler: Callable[[Any], Any],
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        """Run a sync handler with normalized input and emit GCF-first output."""
        normalized_input = self.from_any_to_object(inbound)
        result = handler(normalized_input)
        return self.convert_output(result, session_id=session_id)

    async def process_async(
        self,
        inbound: Any,
        handler: Callable[[Any], Any] | Callable[[Any], Awaitable[Any]],
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        """Run a sync/async handler with normalized input and emit GCF-first output."""
        normalized_input = self.from_any_to_object(inbound)
        result = handler(normalized_input)
        if inspect.isawaitable(result):
            result = await result
        return self.convert_output(result, session_id=session_id)
