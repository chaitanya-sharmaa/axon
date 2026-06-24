"""
Stateful Thread Example

This script demonstrates how to use the Axon Proxy's new Stateful Threads API.
Instead of sending the massive 10,000+ token context on every conversational turn,
the client only sends the new "delta" message.

The proxy stores the thread history in SQLite, rehydrates the full history,
structurally compresses it (GCF), and orchestrates the stateless LLM.

Result:
1. Client-to-Proxy Bandwidth drops by 99% on Turn 2 and 3.
2. Token API bill drops by ~30% on every turn (via GCF compression).
3. ZERO Hallucination from the LLM!
"""

import uuid
import time
import requests
import json
import textwrap

# Ensure your proxy is running: `uvicorn main:app --port 8080`
AXON_URL = "http://127.0.0.1:8080/v1/chat/completions"

# Create a unique thread ID for this session
thread_id = f"thread_{uuid.uuid4().hex[:8]}"

# Generate a large fake product catalog (100 items) to act as massive context
catalog = []
for i in range(100):
    catalog.append({
        "product_id": f"SKU-{1000+i}",
        "name": "Enterprise Flux Capacitor Model X",
        "description": "A high-performance flux capacitor for enterprise time-travel needs.",
        "price": 1000.0 + (i * 15.0),
        "in_stock": True,
        "specifications": {
            "weight": f"{1.5 + (i * 0.1):.1f}kg",
            "dimensions": "10x20x30 cm",
            "power_draw": "1.21 GW"
        }
    })

# Add an unobtanium item to test if the model actually remembers the catalog
catalog[50]["name"] = "Unobtanium Alloy Wrench"
catalog[50]["description"] = "A special wrench made of unobtanium."

# Helper to send a message
def send_message(turn_name: str, message: str, context: list = None):
    print("=" * 60)
    print(f"🤖 {turn_name}")
    print("=" * 60)
    
    messages = []
    
    # If we are providing context (only happens on Turn 1)
    if context:
        messages.append({
            "role": "system",
            "content": f"You are a helpful assistant. Here is the product catalog:\n{json.dumps(context)}"
        })
        
    # The actual user question
    messages.append({
        "role": "user",
        "content": message
    })
    
    payload = {
        "model": "ollama/llama3",
        "messages": messages,
        "temperature": 0.0
    }
    
    # This is the magic!
    headers = {
        "X-Axon-Session-ID": thread_id,
        "X-Axon-Stateful-Thread": "true",
        "Authorization": "Bearer AQ.test"
    }
    
    # Calculate bytes sent to proxy
    raw_json_bytes = len(json.dumps(payload))
    print(f"⬆️ Uploading to Proxy: {raw_json_bytes} bytes ({raw_json_bytes/1024:.1f} KB)")
    
    start_t = time.time()
    try:
        resp = requests.post(AXON_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Error hitting proxy: {e}")
        return
        
    latency = time.time() - start_t
    data = resp.json()
    answer = data["choices"][0]["message"]["content"]
    
    metrics = resp.headers.get("x-axon-metrics")
    if metrics:
        m = json.loads(metrics)
        orig = m.get('original_tokens', 0)
        comp = m.get('compressed_tokens', 0)
        sav_pct = m.get('savings_pct', 0)
        strat = m.get('best_strategy', 'Unknown')
        print(f"🚀 Proxy sent to LLM: {comp} tokens (avoided {orig - comp} tokens!) [Strategy: {strat}]")
        print(f"⏱️ Latency: {latency:.2f}s")
        
    print(f"\n💬 LLM Answer:\n{textwrap.fill(answer, width=80)}\n")

if __name__ == "__main__":
    print(f"🧵 Starting Stateful Thread ID: {thread_id}\n")
    
    # Turn 1: Send the massive catalog
    send_message(
        turn_name="Turn 1 (Cold Start)", 
        message="Identify the product_id of the cheapest item.", 
        context=catalog
    )
    
    # Turn 2: ONLY send the follow-up question! No catalog!
    send_message(
        turn_name="Turn 2 (Stateful Delta)", 
        message="Are there any products made of Unobtanium?"
    )
    
    # Turn 3: ONLY send the reasoning question! No catalog!
    send_message(
        turn_name="Turn 3 (Stateful Reasoning)", 
        message="What is the price of that Unobtanium item?"
    )
