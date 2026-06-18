#!/usr/bin/env python3
"""Multi-turn session benchmark: demonstrate compounding token savings via session dedup."""

import json
import statistics
import urllib.error
import urllib.request
from datetime import datetime

BASE_URL = "http://127.0.0.1:8080"
SESSION_ID = f"bench-{int(datetime.now().timestamp() * 1000)}"


def _post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=10) as resp:
        return json.loads(resp.read())


def simulate_graph_payload(call_num: int) -> dict:
    """Generate realistic graph payload (code + docs with substantial content)."""
    symbols = []
    for i in range(1, 8 + call_num * 2):
        symbols.append({
            "type": "class",
            "name": f"Service{i}",
            "module": "api",
            "docstring": (
                f"Service class for handling requests. Implements async patterns, error handling, "
                f"retry logic, circuit breaking, and resource cleanup. Version {i}.0 with "
                f"enhanced monitoring and observability. Routes to backend {i}. " * 3
            ),
            "methods": ["handle", "validate", "process", "cleanup"],
        })

    for i in range(1, 6 + call_num):
        symbols.append({
            "type": "function",
            "name": f"handle_{i}",
            "module": "api",
            "docstring": (
                f"Request handler for endpoint {i}. Processes incoming data, "
                f"validates against schema, calls downstream services, aggregates results, "
                f"caches outcomes, emits metrics. Handles errors gracefully. " * 2
            ),
            "params": ["request", "context", "config"],
            "returns": "Response",
        })

    edges = []
    for i in range(1, len(symbols) // 2):
        edges.append({
            "from": f"Service{i}",
            "to": f"handle_{i % 5 or 1}",
            "type": "calls",
            "weight": i,
            "metadata": "Dependency chain for service routing and data flow control",
        })

    return {
        "symbols": symbols,
        "edges": edges,
        "metadata": {
            "project": "api-gateway",
            "version": "2.1.0",
            "description": "Microservices gateway with session tracking and deduplication support" * 2,
        },
    }


def run_benchmark() -> dict | None:
    """Run 10 sequential calls with graph payloads in the same session."""
    print("=" * 80)
    print("📊 MULTI-TURN SESSION BENCHMARK (Graph Profile Deduplication)")
    print("=" * 80)
    print(f"Session ID: {SESSION_ID}\n")

    results: dict = {"calls": [], "json_tokens": [], "axon_tokens": [], "savings_pct": []}

    for call_num in range(1, 11):
        payload = simulate_graph_payload(call_num)
        try:
            resp_data = _post("/process", {
                "inbound": payload,
                "handler": "graph_processor",
                "session_id": SESSION_ID,
            })
            metrics = resp_data.get("metrics", {})
            json_tokens = metrics.get("estimated_json_tokens", 0)
            axon_tokens = metrics.get("estimated_optimized_tokens", 0)
            savings_pct = metrics.get("estimated_savings_percent", 0)

            results["calls"].append(call_num)
            results["json_tokens"].append(json_tokens)
            results["axon_tokens"].append(axon_tokens)
            results["savings_pct"].append(savings_pct)

            print(
                f"Call {call_num:2d}: "
                f"Symbols={len(payload['symbols']):2d}, Edges={len(payload['edges']):2d} → "
                f"JSON={json_tokens:5d} → Optimized={axon_tokens:5d} | "
                f"Savings: {savings_pct:5.1f}%"
            )
        except Exception as exc:
            print(f"Call {call_num}: ❌ Failed — {exc}")
            return None

    # Summary statistics
    print("\n" + "=" * 80)
    print("📈 SUMMARY STATISTICS")
    print("=" * 80)

    avg_savings = statistics.mean(results["savings_pct"])
    peak_savings = max(results["savings_pct"])
    total_json = sum(results["json_tokens"])
    total_gcf = sum(results["axon_tokens"])
    overall_savings = ((total_json - total_gcf) / total_json * 100) if total_json else 0

    print(f"\n📊 Savings per call:")
    print(f"   Average:  {avg_savings:.1f}%")
    print(f"   Peak:     {peak_savings:.1f}% (call {results['savings_pct'].index(peak_savings) + 1})")
    print(f"   Min:      {min(results['savings_pct']):.1f}%")

    print(f"\n💾 Total payload compression (10 calls):")
    print(f"   JSON total:       {total_json:,} tokens")
    print(f"   Optimized total:  {total_gcf:,} tokens")
    print(f"   Tokens saved:     {total_json - total_gcf:,}")
    print(f"   Overall savings:  {overall_savings:.1f}%")

    if total_gcf > 0:
        print(f"\n🧠 Context window improvement:")
        print(f"   10 JSON calls at std 4K token limit: {total_json / 4000:.1f}x window usage")
        print(f"   10 Optimized calls:                   {total_gcf / 4000:.1f}x window usage")
        print(f"   Effective expansion:                  {(total_json / total_gcf):.1f}x")

    # Query session memory
    print("\n" + "=" * 80)
    print("💾 SESSION MEMORY")
    print("=" * 80)

    try:
        memory = _get(f"/memory/session/{SESSION_ID}?limit=20")
        print(f"\n✅ Events logged: {memory['history_events']}")
        print(f"✅ Symbols cached: {memory['symbols_cached']}")
        print(f"\n📝 Event types:")
        event_types: dict[str, int] = {}
        for event in memory["recent_events"]:
            etype = event.get("event_type", "unknown")
            event_types[etype] = event_types.get(etype, 0) + 1
        for etype, count in event_types.items():
            print(f"   - {etype}: {count}")
    except Exception as exc:
        print(f"⚠️  Memory query failed: {exc}")

    print("\n" + "=" * 80)
    return results


if __name__ == "__main__":
    run_benchmark()
