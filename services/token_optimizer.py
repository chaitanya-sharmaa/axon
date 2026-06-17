"""Token optimizer: benchmark every available encoding strategy and return the cheapest one.

This is the core cost-saving layer — it sits between the API and the LLM and
automatically picks whichever format produces the fewest tokens for a given payload.

Supported strategies:

  Graph payloads  (payload contains a ``symbols`` list)
  ─────────────────────────────────────────────────────
  gcf_graph         — GCF graph profile (symbol/edge dedup). Best for code-context.
  gcf_session       — TRON for graphs: session-aware dedup, elides previously-seen
                      symbols each turn.  Cumulative savings grow over multi-turn.
  gcf_delta         — TOON for graphs: only changed/added symbols+edges are sent.
                      Ideal when consecutive turns share most of the graph.

  Generic payloads  (any dict / list)
  ────────────────────────────────────
  gcf_generic       — GCF generic profile: compact key=value encoding of any dict.
  gcf_generic_delta — TOON for generics: only the *changed* top-level keys are sent.
                      First turn: full payload.  Subsequent turns in same session:
                      only keys whose values changed vs the previous turn.
  gcf_generic_session — TRON for generics: tracks scalar values seen in previous
                      turns and replaces repeated ones with a short reference token.

  Baseline
  ────────
  json              — Raw JSON. Never wins on real payloads but always available.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Mapping

from gcf import (
    DeltaPayload,
    Edge,
    Payload,
    Session,
    Symbol,
    encode,
    encode_delta,
    encode_generic,
    encode_with_session,
)

# ── Strategy names ─────────────────────────────────────────────────────────────
STRATEGY_GCF_GRAPH = "graph"
STRATEGY_GCF_SESSION = "graph_session"
STRATEGY_GCF_DELTA = "graph_delta"
STRATEGY_GCF_GENERIC = "generic"
STRATEGY_GCF_GENERIC_DELTA = "generic_delta"      # TOON for non-graph
STRATEGY_GCF_GENERIC_SESSION = "generic_session"  # TRON for non-graph
STRATEGY_SCHEMA_VALUES = "schema_values"
STRATEGY_JSON = "json"

ALL_STRATEGIES = [
    STRATEGY_GCF_GRAPH,
    STRATEGY_GCF_SESSION,
    STRATEGY_GCF_DELTA,
    STRATEGY_GCF_GENERIC,
    STRATEGY_GCF_GENERIC_DELTA,
    STRATEGY_GCF_GENERIC_SESSION,
    STRATEGY_SCHEMA_VALUES,
    STRATEGY_JSON,
]


# ── Result containers ──────────────────────────────────────────────────────────

@dataclass
class StrategyResult:
    strategy: str
    encoded: str
    token_estimate: int
    savings_vs_json_pct: float  # positive = cheaper than raw JSON


@dataclass
class OptimizerResult:
    winner: StrategyResult
    all_results: list[StrategyResult]
    json_baseline_tokens: int
    payload_type: str            # "graph" | "generic"

    def to_metrics(self) -> dict[str, Any]:
        comparison: dict[str, Any] = {
            "json": {
                "tokens": self.json_baseline_tokens,
                "savings_pct": 0.0,
            }
        }
        for r in self.all_results:
            comparison[r.strategy] = {
                "tokens": r.token_estimate,
                "savings_pct": r.savings_vs_json_pct,
            }
        return {
            "strategy_used": self.winner.strategy,
            "payload_type": self.payload_type,
            "estimated_json_tokens": self.json_baseline_tokens,
            "estimated_optimized_tokens": self.winner.token_estimate,
            "estimated_savings_percent": self.winner.savings_vs_json_pct,
            "format_comparison": comparison,
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

from services.tokenizer_factory import get_tokenizer_for_model

def _estimate_tokens(text: str, model: str | None = None) -> int:
    """Estimate tokens using the specified model's tokenizer, or a fast heuristic if model is unknown."""
    if model:
        try:
            tokenizer = get_tokenizer_for_model(model)
            return len(tokenizer.encode(text))
        except Exception as e:
            logging.warning(f"Failed to load tokenizer for model '{model}': {e}. Falling back to heuristic.")
    # Fallback to heuristic if model is not provided or tokenizer loading fails
    return max(1, len(text) // 4)

def _savings(json_tokens: int, candidate_tokens: int) -> float:
    if json_tokens == 0:
        return 0.0
    return round((1.0 - candidate_tokens / json_tokens) * 100, 2)


def _build_payload(obj: Mapping) -> Payload | None:
    """Try to build a GCF graph Payload from a dict.  Returns None if not graph-shaped."""
    symbols_raw = obj.get("symbols")
    if not isinstance(symbols_raw, list) or not symbols_raw:
        return None
    symbols: list[Symbol] = []
    for item in symbols_raw:
        if not isinstance(item, Mapping):
            return None
        qn = item.get("qualified_name")
        if not qn:
            name = item.get("name", "unknown")
            module = item.get("module", "")
            qn = f"{module}:{name}" if module else name
        symbols.append(Symbol(
            qualified_name=str(qn),
            kind=str(item.get("kind", item.get("type", "function"))),
            score=float(item.get("score", 1.0)),
            provenance=str(item.get("provenance", "bridge")),
            distance=int(item.get("distance", 0)),
        ))
    edges: list[Edge] = []
    edges_raw = obj.get("edges", [])
    if isinstance(edges_raw, list):
        for item in edges_raw:
            if not isinstance(item, Mapping):
                continue
            src = item.get("source") or item.get("from")
            tgt = item.get("target") or item.get("to")
            if src and tgt:
                edges.append(Edge(
                    source=str(src),
                    target=str(tgt),
                    edge_type=str(item.get("edge_type", item.get("type", "references"))),
                ))
    return Payload(
        tool=str(obj.get("tool", "bridge")),
        token_budget=int(obj.get("token_budget", 0)),
        tokens_used=int(obj.get("tokens_used", 0)),
        pack_root=obj.get("pack_root"),
        symbols=symbols,
        edges=edges,
    )


def _build_generic_delta(current: Any, previous: Any | None) -> Any:
    """TOON for generic dicts: return only the keys that changed vs previous turn.

    - First turn (previous is None): returns the full payload.
    - Subsequent turns: returns a dict of only changed/new top-level keys.
      Deleted keys are represented as ``{"__deleted__": true}``.
    - Non-dict payloads fall back to the full payload.
    """
    if previous is None or not isinstance(current, dict) or not isinstance(previous, dict):
        return current

    delta: dict[str, Any] = {}
    all_keys = set(current) | set(previous)
    for key in all_keys:
        if key not in current:
            delta[key] = {"__deleted__": True}
        elif key not in previous or current[key] != previous[key]:
            delta[key] = current[key]
    return delta if delta else current  # if nothing changed, send full to be safe


def _build_generic_session(current: Any, seen_values: dict[str, str]) -> Any:
    """TRON for generic dicts: replace repeated scalar values with a short ref token.

    Scalars (strings, numbers) that appeared in a previous turn are replaced with
    ``@ref:<key>`` where ``<key>`` is the first key they were stored under.  The
    LLM already has the value from context so this cuts repeated literals.

    ``seen_values`` maps ``str(value) → original_key`` and is mutated in place.
    """
    if not isinstance(current, dict):
        return current

    compressed: dict[str, Any] = {}
    for k, v in current.items():
        if isinstance(v, (str, int, float, bool)) and v is not None:
            vstr = str(v)
            if vstr in seen_values and seen_values[vstr] != k:
                compressed[k] = f"@ref:{seen_values[vstr]}"
            else:
                seen_values[vstr] = k
                compressed[k] = v
        else:
            compressed[k] = v
    return compressed

    """Build a delta payload representing *added* symbols vs. previous set."""
def _build_delta(payload: Payload | None, prev_symbols: list[str] | None) -> DeltaPayload | None:
    """Build a delta payload representing *added* symbols vs. previous set."""
    if payload is None:
        return None
    if prev_symbols is None:
        prev_symbols = []
    prev_set = set(prev_symbols)
    added = [s for s in payload.symbols if s.qualified_name not in prev_set]
    removed = [Symbol(qualified_name=qn, kind="unknown", score=0, provenance="", distance=0)
               for qn in prev_set - {s.qualified_name for s in payload.symbols}]
    return DeltaPayload(
        tool=payload.tool,
        base_root="",
        new_root="gcf_root",
        added=added,
        removed=removed,
        added_edges=payload.edges,
    )


# ── Core optimizer ─────────────────────────────────────────────────────────────

class TokenOptimizer:
    """Try every encoding strategy and return the one with the fewest tokens.

    Parameters
    ----------
    enabled_strategies:
        Subset of ALL_STRATEGIES to benchmark.  Defaults to all.
    """

    def __init__(self, enabled_strategies: list[str] | None = None) -> None:
        self._enabled = set(enabled_strategies or ALL_STRATEGIES)
        # Per-session GCF Session objects for session-aware dedup
        self._sessions: dict[str, Session] = {}
        # Per-session previous symbol sets (for graph delta encoding)
        self._prev_symbols: dict[str, list[str]] = {}
        # Per-session previous generic payloads (for generic TOON delta)
        self._prev_generic: dict[str, Any] = {}
        # Per-session seen scalar values (for generic TRON session dedup)
        self._seen_values: dict[str, dict[str, str]] = {}
        # Per-session schema keys (for generic schema_values dedup)
        self._schema_keys: dict[str, tuple[str, ...]] = {}

    def _get_session(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session()
        return self._sessions[session_id]

    def get_gcf_session(self, session_id: str) -> Session:
        return self._get_session(session_id)

    def estimate_tokens_custom(self, text: str, model: str | None = None) -> int:
        """Public access to the estimation logic."""
        return _estimate_tokens(text, model)

    def _get_prev_symbols(self, session_id: str) -> list[str] | None:
        return self._prev_symbols.get(session_id)

    def _update_prev_symbols(self, session_id: str, payload: Payload) -> None:
        self._prev_symbols[session_id] = [s.qualified_name for s in payload.symbols]

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._prev_symbols.pop(session_id, None)
        self._prev_generic.pop(session_id, None)
        self._seen_values.pop(session_id, None)
        self._schema_keys.pop(session_id, None)

    def optimize(
        self,
        obj: Any,
        session_id: str | None = None,
        model: str | None = None,
        enabled_strategies: list[str] | None = None,
    ) -> OptimizerResult:
        """Benchmark all applicable strategies and return the cheapest result.

        Parameters
        ----------
        obj:
            Already-normalized Python object (dict, list, etc.).
        session_id:
            If provided, enables session-aware (TRON) and delta (TOON) strategies.
        model:
            The target LLM model to use for token estimation.
        enabled_strategies:
            Override per-call; falls back to the instance-level ``enabled_strategies``.
        """
        active = set(enabled_strategies or []) or self._enabled
        json_text = json.dumps(obj, separators=(",", ":"), ensure_ascii=True)
        json_tokens = _estimate_tokens(json_text, model=model)

        # Detect payload type
        payload: Payload | None = None
        is_graph = isinstance(obj, Mapping) and isinstance(obj.get("symbols"), list) and len(obj.get("symbols")) > 0
        payload_type = "graph" if is_graph else "generic"
        if is_graph:
            payload = _build_payload(obj)

        results: list[StrategyResult] = []

        def _add(strategy: str, text: str) -> None:
            t = _estimate_tokens(text, model=model)
            results.append(StrategyResult(
                strategy=strategy,
                encoded=text,
                token_estimate=t,
                savings_vs_json_pct=_savings(json_tokens, t),
            ))

        # ── GCF graph ──────────────────────────────────────────────────────────
        if STRATEGY_GCF_GRAPH in active and payload is not None:
            try:
                _add(STRATEGY_GCF_GRAPH, encode(payload))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_GCF_GRAPH} failed: {e}", exc_info=False)

        # ── GCF session (TRON-style multi-turn dedup) ──────────────────────────
        if STRATEGY_GCF_SESSION in active and payload is not None and session_id:
            try:
                sess = self._get_session(session_id)
                _add(STRATEGY_GCF_SESSION, encode_with_session(payload, sess))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_GCF_SESSION} failed: {e}", exc_info=False)

        # ── GCF delta (TOON-style change-only encoding) ───────────────────────
        if STRATEGY_GCF_DELTA in active and payload is not None and session_id:
            try:
                prev = self._get_prev_symbols(session_id)
                delta = _build_delta(payload, prev)
                if delta is not None:
                    _add(STRATEGY_GCF_DELTA, encode_delta(delta))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_GCF_DELTA} failed: {e}", exc_info=False)

        # ── GCF generic (universal fallback) ──────────────────────────────────
        if STRATEGY_GCF_GENERIC in active:
            try:
                _add(STRATEGY_GCF_GENERIC, encode_generic(obj))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_GCF_GENERIC} failed: {e}", exc_info=False)

        # ── GCF generic delta / TOON for non-graph ────────────────────────────
        if STRATEGY_GCF_GENERIC_DELTA in active and session_id and not is_graph:
            try:
                prev = self._prev_generic.get(session_id)
                delta_obj = _build_generic_delta(obj, prev)
                _add(STRATEGY_GCF_GENERIC_DELTA, encode_generic(delta_obj))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_GCF_GENERIC_DELTA} failed: {e}", exc_info=False)

        # ── GCF generic session / TRON for non-graph ──────────────────────────
        if STRATEGY_GCF_GENERIC_SESSION in active and session_id and not is_graph:
            try:
                seen = self._seen_values.setdefault(session_id, {})
                session_obj = _build_generic_session(obj, seen)
                _add(STRATEGY_GCF_GENERIC_SESSION, encode_generic(session_obj))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_GCF_GENERIC_SESSION} failed: {e}", exc_info=False)

        # ── Schema values ───────────────────────────────────────────────────────
        if STRATEGY_SCHEMA_VALUES in active and session_id and not is_graph and isinstance(obj, dict):
            try:
                # Check if all values are scalars (for flat data)
                if all(isinstance(v, (str, int, float, bool)) for v in obj.values()):
                    current_keys = tuple(obj.keys())
                    prev_keys = self._schema_keys.get(session_id)
                    if prev_keys == current_keys:
                        # Keys match exactly, send only values
                        encoded = ",".join(str(v) for v in obj.values())
                    else:
                        # First turn or keys changed, send key=value
                        encoded = ",".join(f"{k}={v}" for k, v in obj.items())
                    _add(STRATEGY_SCHEMA_VALUES, encoded)
                    
                    self._schema_keys[session_id] = current_keys
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_SCHEMA_VALUES} failed: {e}", exc_info=False)

        # ── JSON baseline ──────────────────────────────────────────────────────
        if STRATEGY_JSON in active:
            _add(STRATEGY_JSON, json_text)

        # Pick winner by token count (fewest wins; strategy order breaks ties)
        strategy_order = {s: i for i, s in enumerate(ALL_STRATEGIES)}
        winner = min(results, key=lambda r: (r.token_estimate, strategy_order.get(r.strategy, 99)))

        # Update session state for next turn
        if session_id and payload is not None:
            self._update_prev_symbols(session_id, payload)
        if session_id and not is_graph:
            self._prev_generic[session_id] = obj

        return OptimizerResult(
            winner=winner,
            all_results=results,
            json_baseline_tokens=json_tokens,
            payload_type=payload_type,
        )
