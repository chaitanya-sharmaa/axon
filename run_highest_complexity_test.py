import time
import json
from fastapi.testclient import TestClient
from app import app
import os
from dotenv import load_dotenv

load_dotenv()

client = TestClient(app)

def create_massive_payload():
    items = []
    # 250 highly nested items to create a massive context window load
    for i in range(250):
        items.append({
            "product_id": f"SKU-{1000+i}",
            "name": f"Enterprise Flux Capacitor Model {i}",
            "description": "A highly advanced multi-dimensional tool for resolving temporal paradoxes.",
            "price": 1000.0 + (i * 15),
            "stock": 50 - (i % 10),
            "specifications": {
                "weight": f"{1.5 + (i * 0.1)}kg",
                "dimensions": {
                    "width": "10cm",
                    "height": "15cm",
                    "depth": "20cm"
                },
                "material": "Unobtanium alloy",
                "power_source": "Plutonium reaction / Lightning"
            },
            "reviews": [
                {"user": "DocB", "rating": 5, "comment": "Great Scott! This thing really works. Highly recommended for any time traveler."},
                {"user": "MartyM", "rating": 4, "comment": "Heavy. But it gets the job done."}
            ]
        })
    return items

def run_test():
    payload = create_massive_payload()
    json_payload_str = json.dumps(payload)
    print(f"Generated Payload: 250 complex items. Raw length: {len(json_payload_str)} characters.")
    
    # We ask the LLM to identify the most expensive item based on this massive structure.
    messages = [
        {"role": "system", "content": "You are a helpful data analyst. Read the following e-commerce catalog data and answer the user's question."},
        {"role": "user", "content": json_payload_str},
        {"role": "user", "content": "What is the product_id of the most expensive item, and exactly how much does it cost? Output strictly in JSON format: {\"product_id\": \"...\", \"price\": ...}"}
    ]
    
    req_body = {
        "model": "gemini/gemini-2.5-flash",
        "messages": messages,
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    
    print("Sending massive payload through Axon Bridge...")
    start_time = time.time()
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    response = client.post(
        "/v1/chat/completions",
        json=req_body,
        headers={"Authorization": f"Bearer {api_key}"}
    )
    
    latency = time.time() - start_time
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return
        
    metrics = response.headers.get("x-axon-metrics")
    cost_saved = response.headers.get("x-axon-cost-saved-usd")
    data = response.json()
    
    print("-" * 50)
    print("✅ TEST COMPLETE")
    print(f"Latency: {latency:.2f} seconds")
    print("\nMetrics:")
    if metrics:
        m = json.loads(metrics)
        print(f"  - Original Tokens: {m.get('original_tokens')}")
        print(f"  - Compressed Tokens: {m.get('compressed_tokens')}")
        print(f"  - Savings: {m.get('savings_pct')}%")
    if cost_saved:
        print(f"  - Estimated Cost Saved: ${cost_saved}")
        
    print("\nLLM Answer (Should be SKU-1249 with price 4735.0):")
    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    print(answer)

if __name__ == "__main__":
    run_test()
