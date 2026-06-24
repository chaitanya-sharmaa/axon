"""Token optimizer: benchmark every available encoding strategy and return the cheapest one.

This is the core cost-saving layer — it sits between the API and the LLM and
automatically picks whichever format produces the fewest tokens for a given payload.

Supported strategies:

  Graph payloads  (payload contains a ``symbols`` list)
  ─────────────────────────────────────────────────────
  axon_graph         — Axon graph profile (symbol/edge dedup). Best for code-context.
  axon_session       — TRON for graphs: session-aware dedup, elides previously-seen
                      symbols each turn.  Cumulative savings grow over multi-turn.
  axon_delta         — TOON for graphs: only changed/added symbols+edges are sent.
                      Ideal when consecutive turns share most of the graph.

  Generic payloads  (any dict / list)
  ────────────────────────────────────
  axon_generic       — Axon generic profile: compact key=value encoding of any dict.
  axon_generic_delta — TOON for generics: only the *changed* top-level keys are sent.
                      First turn: full payload.  Subsequent turns in same session:
                      only keys whose values changed vs the previous turn.
  axon_generic_session — TRON for generics: tracks scalar values seen in previous
                      turns and replaces repeated ones with a short reference token.

  Baseline
  ────────
  json              — Raw JSON. Never wins on real payloads but always available.
"""

from __future__ import annotations

import collections
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
import re

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

# ── Strategy names ─────────────────────────────────────────────────────────────
STRATEGY_AXON_GRAPH = "graph"
STRATEGY_AXON_SESSION = "graph_session"
STRATEGY_AXON_DELTA = "graph_delta"
STRATEGY_AXON_GENERIC = "generic"
STRATEGY_AXON_GENERIC_DELTA = "generic_delta"      # TOON for non-graph
STRATEGY_AXON_GENERIC_SESSION = "generic_session"  # TRON for non-graph
STRATEGY_SCHEMA_VALUES = "schema_values"
STRATEGY_JSON = "json"

# Semantic Aliases requested by User
STRATEGY_GCF = "gcf"
STRATEGY_TOON = "toon"
STRATEGY_TRON = "tron"

ALL_STRATEGIES = [
    STRATEGY_AXON_GRAPH,
    STRATEGY_AXON_SESSION,
    STRATEGY_AXON_DELTA,
    STRATEGY_AXON_GENERIC,
    STRATEGY_AXON_GENERIC_DELTA,
    STRATEGY_AXON_GENERIC_SESSION,
    STRATEGY_SCHEMA_VALUES,
    STRATEGY_JSON,
    STRATEGY_GCF,
    STRATEGY_TOON,
    STRATEGY_TRON,
]


# ── LRU session cache ──────────────────────────────────────────────────────────

from cachetools import TTLCache

class _TTLDict(TTLCache):
    """TTLCache that silently evicts the oldest entry based on time or size.
    
    All per-session dicts in ``TokenOptimizer`` use this so that
    a long-running server cannot accumulate unbounded session state.
    """
    def __init__(self, maxsize: int = 1024, ttl: int = 3600, *args, **kwargs) -> None:
        super().__init__(maxsize=maxsize, ttl=ttl, *args, **kwargs)

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]


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


def _prune_context(symbols: list[Symbol], query: str | None) -> list[Symbol]:
    """Prune bottom 25% of irrelevant symbols if the payload is large and a query exists."""
    if not query or len(symbols) < 50:
        return symbols
        
    query_terms = set(query.lower().replace(".", " ").replace("_", " ").split())
    if not query_terms:
        return symbols
        
    scored = []
    if BM25Okapi:
        # Use BM25 for advanced contextual pruning
        corpus = []
        for s in symbols:
            desc = f"{s.qualified_name} {s.kind} {s.provenance}"
            corpus.append(desc.lower().split())
        
        bm25 = BM25Okapi(corpus)
        tokenized_query = query.lower().split()
        bm25_scores = bm25.get_scores(tokenized_query)
        
        for idx, s in enumerate(symbols):
            # Combine BM25 normalized score with native payload score
            final_score = s.score + (bm25_scores[idx] * 2.0)
            scored.append((final_score, s))
    else:
        # Fallback to string overlap
        for s in symbols:
            name_terms = set(s.qualified_name.lower().replace(".", " ").replace("_", " ").split())
            overlap = len(query_terms.intersection(name_terms))
            final_score = s.score + (overlap * 2.0)
            scored.append((final_score, s))
        
    # Sort highest score first
    scored.sort(key=lambda x: x[0], reverse=True)
    keep_count = max(10, int(len(symbols) * 0.75))
    return [s for _, s in scored[:keep_count]]


def _build_payload(obj: Mapping) -> Payload | None:
    """Try to build a Axon graph Payload from a dict.  Returns None if not graph-shaped."""
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
        try:
            score = float(item.get("score", 1.0))
        except (ValueError, TypeError):
            score = 1.0
            
        symbols.append(Symbol(
            qualified_name=str(qn),
            kind=str(item.get("kind", item.get("type", "function"))),
            score=score,
            provenance=str(item.get("provenance", "bridge")),
            distance=int(item.get("distance", 0)),
        ))
        
    query = str(obj.get("query", "")) or str(obj.get("prompt", ""))
    symbols = _prune_context(symbols, query)
    
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


def _build_generic_delta(current: Any, previous: Any) -> Any:
    """Build a recursive delta between two generic dicts or lists.

    - First turn (previous is None): returns the full payload.
    - Subsequent turns: returns a dict of only changed/new nested keys.
      Deleted keys are represented as ``{"__deleted__": true}``.
    - Non-dict/list payloads fall back to the full payload.
    """
    if previous is None:
        return current
        
    if isinstance(current, dict) and isinstance(previous, dict):
        delta: dict[str, Any] = {}
        all_keys = set(current) | set(previous)
        for key in all_keys:
            if key not in current:
                delta[key] = {"__deleted__": True}
            elif key not in previous:
                delta[key] = current[key]
            else:
                sub_delta = _build_generic_delta(current[key], previous[key])
                if sub_delta is not None:
                    delta[key] = sub_delta
        return delta if delta else None
        
    if isinstance(current, list) and isinstance(previous, list):
        if current == previous:
            return None
        return current
        
    if current == previous:
        return None
        
    return current


def _build_generic_session(current: Any, seen_values: dict[str, int]) -> Any:
    """TRON for generic dicts and lists: recursively replace repeated scalar values with a short ref token.

    Scalars (strings, numbers) that appeared in a previous turn are replaced with
    ``@ref:<id>`` where ``<id>`` is a unique integer ID assigned during encoding.
    
    ``seen_values`` maps ``str(value) → int`` and is mutated in place.
    """
    if isinstance(current, dict):
        compressed_dict: dict[str, Any] = {}
        for k, v in current.items():
            compressed_dict[k] = _build_generic_session(v, seen_values)
        return compressed_dict
        
    elif isinstance(current, list):
        compressed_list: list[Any] = []
        for v in current:
            compressed_list.append(_build_generic_session(v, seen_values))
        return compressed_list
        
    elif isinstance(current, (str, int, float, bool)):
        vstr = str(current)
        if vstr in seen_values:
            # ONLY return ref if the ref is actually shorter than the string itself
            ref_str = f"@ref:{seen_values[vstr]}"
            if len(ref_str) < len(vstr):
                return ref_str
            return current
        else:
            next_id = len(seen_values) + 1
            seen_values[vstr] = next_id
            return current
    else:
        return current


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
        new_root="axon_root",
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

    def __init__(self, enabled_strategies: list[str] | None = None, max_sessions: int = 1000) -> None:
        self._enabled = set(enabled_strategies or ALL_STRATEGIES)
        self._max_sessions = max_sessions
        # Per-session Axon Session objects for session-aware dedup
        self._sessions: _TTLDict = _TTLDict(maxsize=max_sessions)
        # Per-session previous symbol sets (for graph delta encoding)
        self._prev_symbols: _TTLDict = _TTLDict(maxsize=max_sessions)
        # Per-session previous generic payloads (for generic TOON delta)
        self._prev_generic: _TTLDict = _TTLDict(maxsize=max_sessions)
        # Per-session seen scalar values (for generic TRON session dedup)
        self._seen_values: _TTLDict = _TTLDict(maxsize=max_sessions)
        # Per-session schema keys (for generic schema_values dedup)
        self._schema_keys: _TTLDict = _TTLDict(maxsize=max_sessions)
        # ML heuristic: track strategy win streaks per session to fast-path optimization
        self._strategy_wins: _TTLDict = _TTLDict(maxsize=max_sessions)
        # Payload cache to skip redundant optimizations
        self._payload_cache: _TTLDict = _TTLDict(maxsize=4096)

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
        self._strategy_wins.pop(session_id, None)

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
        
        # ── Payload Caching ────────────────────────────────────────────────────
        # Hash the payload to quickly return cached optimizations for exact matches
        cache_key = None
        if not session_id:
            cache_key = hash((json_text, model, tuple(sorted(active))))
            if cache_key in self._payload_cache:
                return self._payload_cache[cache_key]
            
        json_tokens = _estimate_tokens(json_text, model=model)

        # Detect payload type
        payload: Payload | None = None
        is_graph = isinstance(obj, Mapping) and isinstance(obj.get("symbols"), list) and len(obj.get("symbols")) > 0
        payload_type = "graph" if is_graph else "generic"
        if is_graph:
            payload = _build_payload(obj)

        # Strategy Auto-Tuning: Fast-path if we have a stable winner
        if session_id:
            history = self._strategy_wins.get(session_id, {})
            strat, count = history.get(payload_type, (None, 0))
            if count >= 3 and strat in active:
                # We have a stable winner (won 3+ times in a row). 
                # Skip benchmarking other strategies to save CPU, just compare to JSON baseline.
                active = {strat, STRATEGY_JSON}

        results: list[StrategyResult] = []

        def _add(strategy: str, text: str) -> None:
            t = _estimate_tokens(text, model=model)
            results.append(StrategyResult(
                strategy=strategy,
                encoded=text,
                token_estimate=t,
                savings_vs_json_pct=_savings(json_tokens, t),
            ))

        # ── Axon graph ──────────────────────────────────────────────────────────
        if STRATEGY_AXON_GRAPH in active and payload is not None:
            try:
                _add(STRATEGY_AXON_GRAPH, encode(payload))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_AXON_GRAPH} failed: {e}", exc_info=False)

        # ── Axon session (TRON-style multi-turn dedup) ──────────────────────────
        if STRATEGY_AXON_SESSION in active and payload is not None and session_id:
            try:
                sess = self._get_session(session_id)
                _add(STRATEGY_AXON_SESSION, encode_with_session(payload, sess))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_AXON_SESSION} failed: {e}", exc_info=False)

        # ── Axon delta (TOON-style change-only encoding) ───────────────────────
        if STRATEGY_AXON_DELTA in active and payload is not None and session_id:
            try:
                prev = self._get_prev_symbols(session_id)
                delta = _build_delta(payload, prev)
                if delta is not None:
                    _add(STRATEGY_AXON_DELTA, encode_delta(delta))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_AXON_DELTA} failed: {e}", exc_info=False)

        # ── Axon generic (universal fallback) ──────────────────────────────────
        if STRATEGY_AXON_GENERIC in active:
            try:
                _add(STRATEGY_AXON_GENERIC, encode_generic(obj))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_AXON_GENERIC} failed: {e}", exc_info=False)

        # ── Axon generic delta / TOON for non-graph ────────────────────────────
        if STRATEGY_AXON_GENERIC_DELTA in active and session_id and not is_graph:
            try:
                prev = self._prev_generic.get(session_id)
                delta_obj = _build_generic_delta(obj, prev)
                _add(STRATEGY_AXON_GENERIC_DELTA, encode_generic(delta_obj))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_AXON_GENERIC_DELTA} failed: {e}", exc_info=False)

        # ── Axon generic session / TRON for non-graph ──────────────────────────
        if STRATEGY_AXON_GENERIC_SESSION in active or STRATEGY_TRON in active:
            if session_id and not is_graph:
                try:
                    seen = self._seen_values.setdefault(session_id, {})
                    session_obj = _build_generic_session(obj, seen)
                    
                    strat_name = STRATEGY_TRON if STRATEGY_TRON in active else STRATEGY_AXON_GENERIC_SESSION
                    _add(strat_name, encode_generic(session_obj))
                except Exception as e:
                    logging.warning(f"Strategy {STRATEGY_TRON} failed: {e}", exc_info=False)

        # ── GCF (Graph Configuration Format) ───────────────────────────────────
        if STRATEGY_GCF in active:
            try:
                _add(STRATEGY_GCF, encode_generic(obj))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_GCF} failed: {e}", exc_info=False)

        # ── TOON (Delta Protocol) ──────────────────────────────────────────────
        if STRATEGY_TOON in active and session_id:
            try:
                if is_graph:
                    prev = self._get_prev_symbols(session_id)
                    delta = _build_delta(payload, prev)
                    if delta is not None:
                        _add(STRATEGY_TOON, encode_delta(delta))
                else:
                    prev = self._prev_generic.get(session_id)
                    delta_obj = _build_generic_delta(obj, prev)
                    _add(STRATEGY_TOON, encode_generic(delta_obj))
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_TOON} failed: {e}", exc_info=False)

        # ── Schema values ───────────────────────────────────────────────────────
        if STRATEGY_SCHEMA_VALUES in active and session_id and not is_graph and isinstance(obj, dict):
            try:
                def _flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
                    items = []
                    for k, v in d.items():
                        new_key = f"{parent_key}{sep}{k}" if parent_key else k
                        if isinstance(v, dict):
                            items.extend(_flatten_dict(v, new_key, sep=sep).items())
                        elif isinstance(v, list):
                            items.append((new_key, str(v)))
                        else:
                            items.append((new_key, v))
                    return dict(items)

                flat_obj = _flatten_dict(obj)
                current_keys = tuple(flat_obj.keys())
                prev_keys = self._schema_keys.get(session_id)
                if prev_keys == current_keys:
                    # Keys match exactly, send only values
                    encoded = ",".join(str(v) for v in flat_obj.values())
                else:
                    # First turn or keys changed, send key=value
                    encoded = ",".join(f"{k}={v}" for k, v in flat_obj.items())
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

        # Record strategy win for auto-tuning
        if session_id:
            history = self._strategy_wins.setdefault(session_id, {})
            current_winner, count = history.get(payload_type, (None, 0))
            if winner.strategy == current_winner:
                history[payload_type] = (winner.strategy, count + 1)
            else:
                history[payload_type] = (winner.strategy, 1)

        result = OptimizerResult(
            winner=winner,
            all_results=results,
            json_baseline_tokens=json_tokens,
            payload_type=payload_type,
        )
        
        if cache_key is not None:
            self._payload_cache[cache_key] = result
        return result

# ── Agentic Feature Suite ──────────────────────────────────────────────────────



def prune_tools(tools: list[dict[str, Any]], query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Dynamically prune irrelevant tools from the schema using BM25.
    If the user's query is short or tools are few, it returns them all.
    """
    if not BM25Okapi or not query or len(tools) <= top_k:
        return tools
    
    # Create corpus from tool descriptions/names
    corpus = []
    for t in tools:
        func = t.get("function", {})
        desc = func.get("description", "") + " " + func.get("name", "")
        corpus.append(desc.lower().split())
        
    bm25 = BM25Okapi(corpus)
    tokenized_query = query.lower().split()
    
    # Get top_k tools
    top_tools = bm25.get_top_n(tokenized_query, tools, n=top_k)
    return top_tools

def minify_scratchpad(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Iterate over messages. For older assistant messages, strip <thought>...</thought> blocks
    and truncate long internal monologues to compress context.
    """
    if len(messages) <= 2:
        return messages
        
    minified = []
    # Leave the last 2 messages intact
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), str) and i < len(messages) - 2:
            content = msg["content"]
            # Strip <thought>...</thought> tags and their contents
            content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL)
            msg["content"] = content.strip()
        minified.append(msg)
    return minified

