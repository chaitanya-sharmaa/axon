#!/usr/bin/env python3
"""
Benchmark the performance (latency) of each individual encoding strategy.

This script measures the raw encoding time for different payload types to help
understand the performance trade-offs of each compression format.
"""
import timeit
import json
from typing import Any, Callable, Dict

# Add project root to path to allow direct imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.token_optimizer import (
    _SessionState,
    _build_payload,
    _build_generic_delta,
    _build_generic_session,
    _build_delta,
    _encode_schema_values_strategy,
    tokenizer,
)
from gcf import (
    encode,
    encode_delta,
    encode_generic,
    encode_with_session,
)

NUMBER_OF_RUNS = 1000

# --- Payloads for benchmarking ---

small_flat_payload = {"id": 123, "user": "test", "value": 45.6, "active": True}
small_flat_payload_2 = {"id": 124, "user": "test", "value": 47.1, "active": False}

medium_nested_payload = {
    "user": {"id": 123, "name": "alice", "roles": ["admin", "editor"]},
    "request": {"path": "/api/data", "method": "GET"},
    "metrics": {"latency": 150, "retries": 0},
    "status": "success",
}
medium_nested_payload_2 = {
    "user": {"id": 123, "name": "alice", "roles": ["admin", "editor"]},
    "request": {"path": "/api/data", "method": "POST"},  # changed
    "metrics": {"latency": 180, "retries": 1},  # changed
    "status": "success",
}

large_graph_payload = {
    "symbols": [{"qualified_name": f"pkg.Service{i}", "kind": "class"} for i in range(20)],
    "edges": [{"source": f"pkg.Service{i}", "target": f"pkg.Service{i+1}", "edge_type": "calls"} for i in range(19)]
}
large_graph_payload_2 = {
    **large_graph_payload,
    "symbols": large_graph_payload["symbols"] + [{"qualified_name": "pkg.Logger", "kind": "class"}],
    "edges": large_graph_payload["edges"] + [{"source": "pkg.Logger", "target": "pkg.Service0", "edge_type": "logs_to"}]
}


def run_benchmark(title: str, payload: Any, strategies: Dict[str, Callable[[], str]]):
    """Runs timeit for each strategy and prints a formatted table."""
    print("\n" + "=" * 80)
    print(f"  BENCHMARK: {title}")
    print(f"  (running {NUMBER_OF_RUNS} iterations per strategy)")
    print("=" * 80)
    print(f"{'Strategy':<25} | {'Avg Latency (μs)':>20} | {'Tokens':>8} | {'Savings':>10}")
    print("-" * 80)

    results = []
    json_tokens = 0

    for name, encode_func in strategies.items():
        try:
            # Warm-up run
            encoded_text = encode_func()

            # Timing
            total_time = timeit.timeit(encode_func, number=NUMBER_OF_RUNS)
            avg_latency_us = (total_time / NUMBER_OF_RUNS) * 1_000_000

            # Token estimation
            tokens = tokenizer.estimate_tokens(encoded_text)
            if name == "json":
                json_tokens = tokens

            results.append({
                "name": name,
                "latency": avg_latency_us,
                "tokens": tokens,
            })
        except Exception as e:
            print(f"{name:<25} | {'ERROR':>20} | {'N/A':>8} | {'N/A':>10} ({e})")

    # Sort by latency and print
    results.sort(key=lambda x: x["latency"])
    for res in results:
        savings = 0.0
        if json_tokens > 0 and res["name"] != "json":
            savings = (1 - res["tokens"] / json_tokens) * 100

        print(f"{res['name']:<25} | {res['latency']:>17.2f} μs | {res['tokens']:>8} | {savings:9.1f}%")


def main():
    """Define and run all benchmarks."""

    # --- Benchmark 1: Small, Flat Payload ---
    session_state_flat = _SessionState()
    _encode_schema_values_strategy(small_flat_payload, session_state_flat)  # Prime schema

    flat_strategies = {
        "json": lambda: json.dumps(small_flat_payload_2),
        "generic": lambda: encode_generic(small_flat_payload_2),
        "generic_delta": lambda: encode_generic(_build_generic_delta(small_flat_payload_2, small_flat_payload.copy())),
        "generic_session": lambda: encode_generic(_build_generic_session(small_flat_payload_2, session_state_flat.seen_values.copy())),
        "schema_values": lambda: _encode_schema_values_strategy(small_flat_payload_2, session_state_flat),
    }
    run_benchmark("Small, Flat Payload (e.g., Telemetry)", small_flat_payload_2, flat_strategies)

    # --- Benchmark 2: Medium, Nested Payload ---
    session_state_nested = _SessionState()
    _build_generic_session(medium_nested_payload, session_state_nested.seen_values)  # Prime session

    nested_strategies = {
        "json": lambda: json.dumps(medium_nested_payload_2),
        "generic": lambda: encode_generic(medium_nested_payload_2),
        "generic_delta": lambda: encode_generic(_build_generic_delta(medium_nested_payload_2, medium_nested_payload.copy())),
        "generic_session": lambda: encode_generic(_build_generic_session(medium_nested_payload_2, session_state_nested.seen_values.copy())),
    }
    run_benchmark("Medium, Nested Payload (e.g., API Response)", medium_nested_payload_2, nested_strategies)

    # --- Benchmark 3: Large Graph Payload ---
    p1 = _build_payload(large_graph_payload)
    p2 = _build_payload(large_graph_payload_2)
    session_state_graph = _SessionState()
    encode_with_session(p1, session_state_graph.axon_session)  # Prime session

    graph_strategies = {
        "json": lambda: json.dumps(large_graph_payload_2),
        "graph": lambda: encode(p2),
        "graph_delta": lambda: encode_delta(_build_delta(p2, [s.qualified_name for s in p1.symbols])),
        "graph_session": lambda: encode_with_session(p2, Session(state=session_state_graph.axon_session.state)),
    }
    run_benchmark("Large Graph Payload (e.g., Code Context)", large_graph_payload_2, graph_strategies)


if __name__ == "__main__":
    main()