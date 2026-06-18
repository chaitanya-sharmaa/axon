import asyncio
import httpx
import time
import json
import uuid

# Start Axon Bridge locally on port 8080 or assume it's running
AXON_URL = "http://127.0.0.1:8080/process"

PAYLOADS = {
    "Small JSON": {"user": "Alice", "status": "active"},
    "Nested JSON": {"data": {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}},
    "Graph Payload": {
        "symbols": [{"id": 1, "type": "function"}, {"id": 2, "type": "class"}],
        "edges": [{"from": 1, "to": 2, "type": "calls"}]
    },
    "Large List": {"items": [{"id": i, "value": f"item-{i}"} for i in range(100)]},
}

async def run_benchmark():
    session_id = str(uuid.uuid4())
    results = {}
    
    async with httpx.AsyncClient(timeout=30) as client:
        # Wait for API to be ready
        try:
            await client.get("http://127.0.0.1:8080/health/live")
        except Exception:
            print("Axon Bridge is not running on 8080. Please start it first.")
            return

        for name, payload in PAYLOADS.items():
            print(f"Benchmarking {name}...")
            
            # Send once to establish session
            req = {
                "inbound": payload,
                "handler": "echo",
                "session_id": session_id
            }
            
            t0 = time.monotonic()
            res = await client.post(AXON_URL, json=req)
            latency = (time.monotonic() - t0) * 1000
            
            data = res.json()
            metrics = data.get("metrics", {})
            savings = metrics.get("estimated_savings_percent", 0)
            
            # For multi-turn, let's send it 4 more times to simulate a 5-turn session
            if name == "Large List":
                for _ in range(4):
                    res = await client.post(AXON_URL, json=req)
                data = res.json()
                metrics = data.get("metrics", {})
                savings = metrics.get("estimated_savings_percent", 0)
                name = "Large List (5 turns)"
            
            results[name] = {
                "savings": savings,
                "latency_ms": latency
            }
            
    print("\n--- Benchmark Results ---")
    print(json.dumps(results, indent=2))
    
    # Generate Mermaid Chart
    print("\n--- Mermaid Diagram ---")
    print("```mermaid")
    print("xychart-beta")
    print('    title "Axon Token Savings vs JSON Baseline"')
    print(f'    x-axis [{", ".join(f'"{k}"' for k in results.keys())}]')
    print('    y-axis "Savings (%)" 0 --> 100')
    print(f'    bar [{", ".join(str(v["savings"]) for v in results.values())}]')
    print("```")
    
if __name__ == "__main__":
    asyncio.run(run_benchmark())
