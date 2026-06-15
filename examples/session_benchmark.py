#!/usr/bin/env python3
"""Multi-turn session benchmark: demonstrate compounding token savings via session dedup."""

import json
import requests
import statistics
from datetime import datetime

BASE_URL = "http://127.0.0.1:8080"
SESSION_ID = f"bench-{int(datetime.now().timestamp() * 1000)}"


def simulate_graph_payload(call_num: int) -> dict:
    """Generate realistic graph payload (code + docs with substantial content)."""
    # Simulate expanding API module with expanding docstrings and code references
    symbols = []
    for i in range(1, 8 + call_num * 2):
        symbols.append({
            "type": "class",
            "name": f"Service{i}",
            "module": "api",
            "docstring": f"Service class for handling requests. Implements async patterns, error handling, "
                        f"retry logic, circuit breaking, and resource cleanup. Version {i}.0 with "
                        f"enhanced monitoring and observability. Routes to backend {i}. " * 3,
            "methods": [f"handle", f"validate", f"process", f"cleanup"],
        })
    
    for i in range(1, 6 + call_num):
        symbols.append({
            "type": "function",
            "name": f"handle_{i}",
            "module": "api",
            "docstring": f"Request handler for endpoint {i}. Processes incoming data, "
                        f"validates against schema, calls downstream services, aggregates results, "
                        f"caches outcomes, emits metrics. Handles errors gracefully. " * 2,
            "params": ["request", "context", "config"],
            "returns": "Response",
        })
    
    # Edges represent dependencies (repeated for realism)
    edges = []
    for i in range(1, len(symbols) // 2):
        edges.append({
            "from": f"Service{i}",
            "to": f"handle_{i % 5 or 1}",
            "type": "calls",
            "weight": i,
            "metadata": f"Dependency chain for service routing and data flow control"
        })
    
    return {
        "symbols": symbols,
        "edges": edges,
        "metadata": {
            "project": "api-gateway",
            "version": "2.1.0",
            "description": "Microservices gateway with session tracking and deduplication support" * 2
        }
    }


def run_benchmark():
    """Run 10 sequential calls with graph payloads in same session."""
    print("=" * 80)
    print("📊 MULTI-TURN SESSION BENCHMARK (Graph Profile Deduplication)")
    print("=" * 80)
    print(f"Session ID: {SESSION_ID}\n")
    
    results = {
        "calls": [],
        "json_tokens": [],
        "gcf_tokens": [],
        "savings_pct": [],
    }
    
    for call_num in range(1, 11):
        payload = simulate_graph_payload(call_num)
        
        request = {
            "inbound": payload,
            "handler": "graph_processor",
            "session_id": SESSION_ID,
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/process",
                json=request,
                timeout=10,
            )
            resp_data = response.json()
            metrics = resp_data.get("metrics", {})
            
            json_tokens = metrics.get("estimated_json_tokens", 0)
            gcf_tokens = metrics.get("estimated_optimized_tokens", 0)
            savings_pct = metrics.get("estimated_savings_percent", 0)
            
            results["calls"].append(call_num)
            results["json_tokens"].append(json_tokens)
            results["gcf_tokens"].append(gcf_tokens)
            results["savings_pct"].append(savings_pct)
            
            print(
                f"Call {call_num:2d}: "
                f"Symbols={len(payload['symbols']):2d}, Edges={len(payload['edges']):2d} -> "
                f"JSON={json_tokens:5d} -> Optimized={gcf_tokens:5d} | "
                f"Savings: {savings_pct:5.1f}%"
            )
        except Exception as e:
            print(f"Call {call_num}: ❌ Failed — {e}")
            return None
    
    # Print summary statistics
    print("\n" + "=" * 80)
    print("📈 SUMMARY STATISTICS")
    print("=" * 80)
    
    avg_savings = statistics.mean(results["savings_pct"])
    peak_savings = max(results["savings_pct"])
    total_json = sum(results["json_tokens"])
    total_gcf = sum(results["gcf_tokens"])
    overall_savings = ((total_json - total_gcf) / total_json * 100) if total_json else 0
    
    print(f"\n📊 Savings per call:")
    print(f"   Average:  {avg_savings:.1f}%")
    print(f"   Peak:     {peak_savings:.1f}% (call {results['savings_pct'].index(peak_savings) + 1})")
    print(f"   Min:      {min(results['savings_pct']):.1f}%")
    
    print(f"\n💾 Total payload compression (10 calls):")
    print(f"   JSON total:       {total_json:,} tokens")
    print(f"   Optimized total:  {total_gcf:,} tokens")
    print(f"   Bytes saved:      {total_json - total_gcf:,}")
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
        resp = requests.get(f"{BASE_URL}/memory/session/{SESSION_ID}?limit=20", timeout=10)
        if resp.status_code == 200:
            memory = resp.json()
            print(f"\n✅ Events logged: {memory['history_events']}")
            print(f"✅ Symbols cached: {memory['symbols_cached']}")
            print(f"\n📝 Event types:")
            event_types = {}
            for event in memory["recent_events"]:
                etype = event.get("event_type", "unknown")
                event_types[etype] = event_types.get(etype, 0) + 1
            for etype, count in event_types.items():
                print(f"   - {etype}: {count}")
    except Exception as e:
        print(f"⚠️ Memory query failed: {e}")
    
    print("\n" + "=" * 80)
    
    return results


if __name__ == "__main__":
    run_benchmark()
