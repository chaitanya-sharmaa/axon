import httpx
import json
import os
import time

BASE_URL = "http://localhost:8082/v1/chat/completions"
_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
HEADERS = {
    "Content-Type": "application/json",
    "X-Axon-Session-ID": "live-test-session-123",
    "X-Axon-Stateful-Thread": "true",
    "Authorization": f"Bearer {_API_KEY}"
}

def print_result(turn_name, response):
    print(f"\n=============================================")
    print(f"🧪 {turn_name}")
    print(f"=============================================")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return

    try:
        data = response.json()
        print(f"✅ LLM Replied: {data['choices'][0]['message']['content'][:60]}...")
    except Exception as e:
        print(f"Failed to parse LLM response: {response.text}")

    metrics_str = response.headers.get("x-axon-metrics")
    cache_str = response.headers.get("x-axon-cache", "MISS")
    
    if metrics_str:
        print(f"RAW METRICS HEADER: {metrics_str}")
        metrics = json.loads(metrics_str)
        print(f"🚀 AXON SAVINGS: {metrics.get('savings_pct', 0)}%")
        print(f"   Original Tokens : {metrics.get('original_tokens', 0)}")
        print(f"   Billed Tokens   : {metrics.get('compressed_tokens', 0)}")
        print(f"   Winning Strategy: {metrics.get('strategy', 'Unknown')}")
        print(f"   Cache Hit       : {cache_str}")
    else:
        print("❌ No x-axon-metrics header found in response!")

def run_live_test():
    with httpx.Client(timeout=60.0) as client:
        # Realistic Payload: E-commerce Product Catalog
        product_catalog = [
            {"id": "p1", "name": "Laptop", "category": "electronics", "price": 999.99, "stock": 15},
            {"id": "p2", "name": "Mouse", "category": "electronics", "price": 49.99, "stock": 100},
            {"id": "p3", "name": "Keyboard", "category": "electronics", "price": 129.99, "stock": 42},
            {"id": "p4", "name": "Monitor", "category": "electronics", "price": 299.99, "stock": 8},
            {"id": "p5", "name": "HDMI Cable", "category": "accessories", "price": 15.99, "stock": 250},
        ]
        
        headers_stateless = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_API_KEY}"
        }

        # 1. Turn 1 (Identify cheapest item)
        # We send raw JSON in the user message so Axon's TokenOptimizer can compress it.
        # We put the instruction in a system prompt.
        req_body_turn1 = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a shopping assistant. Answer based on the provided JSON product catalog."},
                {"role": "user", "content": json.dumps(product_catalog)},
                {"role": "user", "content": "What is the cheapest item?"}
            ]
        }
        
        print("\nSending Turn 1 (Stateless / Schema Flattening)...")
        start = time.time()
        res1 = client.post(BASE_URL, json=req_body_turn1, headers=headers_stateless)
        print(f"Time: {time.time() - start:.2f}s")
        print_result("Turn 1 (Identify cheapest item)", res1)

        # 2. Turn 2 (Exact Repeat of Turn 1 -> KV Cache Hit)
        print("\nSending Turn 2 (KV Cache Check)...")
        start = time.time()
        res2 = client.post(BASE_URL, json=req_body_turn1, headers=headers_stateless)
        print(f"Time: {time.time() - start:.2f}s")
        print_result("Turn 2 (Exact repeat of Turn 1 - Exact-Match Cache)", res2)

        # 3. Turn 3 (Delta / Stateful thread - Network Savings)
        # In a stateful thread, the client only sends the FOLLOW-UP question. 
        # Axon will rehydrate the previous messages (the catalog) from memory!
        req_body_turn3 = {
            "model": "gpt-4o-mini",
            "messages": [
                # Client ONLY sends the new question! (Massive network bandwidth savings)
                {"role": "user", "content": "What about the most expensive item?"}
            ]
        }
        
        headers_stateful = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_API_KEY}",
            "X-Axon-Session-ID": "live-test-session-ecommerce",
            "X-Axon-Stateful-Thread": "true"
        }
        
        # But wait, to test stateful threads, Turn 1 needed to be sent with stateful headers
        # so Axon could store the history in SQLite!
        # Let's run a setup stateful request first.
        print("\n[Setup] Seeding stateful session for Turn 3...")
        client.post(BASE_URL, json=req_body_turn1, headers=headers_stateful)

        print("\nSending Turn 3 (Network Delta)...")
        start = time.time()
        res3 = client.post(BASE_URL, json=req_body_turn3, headers=headers_stateful)
        print(f"Time: {time.time() - start:.2f}s")
        print_result("Turn 3 (Follow-up question - Network Delta)", res3)

if __name__ == "__main__":
    run_live_test()
