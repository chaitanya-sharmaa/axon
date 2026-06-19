import json
import time
from core.app_config import axon_service

# Define the Payloads for the Benchmarks

# 1. Simple Flat JSON
small_flat_payload = {"id": 123, "user": "test", "value": 45.6, "active": True}

# 2. Medium Nested JSON
medium_nested_payload = {
    "user": {"id": 123, "name": "alice", "roles": ["admin", "editor"]},
    "request": {"path": "/api/data", "method": "GET"},
    "metrics": {"latency": 150, "retries": 0},
    "status": "success",
}

# 3. Graph Payload
large_graph_payload = {
    "symbols": [{"qualified_name": f"pkg.Service{i}", "kind": "class"} for i in range(20)],
    "edges": [{"source": f"pkg.Service{i}", "target": f"pkg.Service{i+1}", "edge_type": "calls"} for i in range(19)]
}

# 4. Highest Complexity Payload (Nested attributes with repeating schemas)
highest_complexity_payload = [
    {
        "id": f"record_{i}",
        "metadata": {
            "timestamp": "2026-06-19T12:00:00Z",
            "source": "database_shard_1",
            "tags": ["urgent", "processed", f"tag_{i % 5}"],
            "nested_attributes": {
                "level1": {
                    "level2": {
                        "level3": {
                            "value": i * 1000,
                            "is_active": i % 2 == 0
                        }
                    }
                }
            }
        },
        "content": f"This is an incredibly long and repetitive string of text intended to simulate a RAG document chunk or database row for record {i}." * 5
    }
    for i in range(100)
]

use_cases = {
    "Telemetry Event (Flat JSON)": small_flat_payload,
    "API Response (Nested JSON)": medium_nested_payload,
    "Code Context (Graph/Nodes)": large_graph_payload,
    "RAG Chunk (Highest Complexity)": highest_complexity_payload
}

results = []

for name, payload in use_cases.items():
    # Cold Start (No Session)
    t0 = time.time()
    result = axon_service._optimizer.optimize({"role": "user", "content": payload}, session_id=f"bench_session_{name}")
    latency_ms = (time.time() - t0) * 1000
    
    # Session Match (2nd turn)
    t1 = time.time()
    result_session = axon_service._optimizer.optimize({"role": "user", "content": payload}, session_id=f"bench_session_{name}")
    session_latency_ms = (time.time() - t1) * 1000
    
    results.append({
        "Use Case": name,
        "Original Tokens (JSON)": result.json_baseline_tokens,
        "Axon Cold Tokens": result.winner.token_estimate,
        "Cold Savings": f"{result.winner.savings_vs_json_pct}%",
        "Axon Multi-Turn Tokens": result_session.winner.token_estimate,
        "Multi-Turn Savings": f"{result_session.winner.savings_vs_json_pct}%",
        "Avg Latency (ms)": f"{(latency_ms + session_latency_ms) / 2:.2f}ms",
        "Winning Strategy": result.winner.strategy
    })

# Format as Markdown Table
print("| Use Case | Original Tokens | Axon Cold Tokens | Cold Savings % | Axon Multi-Turn Tokens | Multi-Turn Savings % | Latency | Winning Strategy |")
print("|---|---|---|---|---|---|---|---|")
for r in results:
    print(f"| {r['Use Case']} | {r['Original Tokens (JSON)']} | {r['Axon Cold Tokens']} | {r['Cold Savings']} | {r['Axon Multi-Turn Tokens']} | {r['Multi-Turn Savings']} | {r['Avg Latency (ms)']} | {r['Winning Strategy']} |")
