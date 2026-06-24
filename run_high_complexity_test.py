import time
import json
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_extreme_complexity():
    print("🚀 AXON BRIDGE — EXTREME COMPLEXITY TEST")
    
    # Very complex prompt to trigger the Smart Router and push the LLM
    prompt = """
    You are an expert Principal Software Engineer. 
    I need you to design a highly scalable, fault-tolerant, event-driven microservices architecture for a global ride-sharing application.
    
    Requirements:
    1. Handle 10 million active users and 1 million concurrent drivers.
    2. Real-time geospatial tracking with < 50ms latency.
    3. Eventual consistency for payments and billing.
    4. Provide a detailed component diagram description.
    5. Explain your database choices (e.g., PostgreSQL vs Cassandra vs Redis) and why.
    6. Think step-by-step and deduce the architectural constraints before providing the final design.
    """
    
    messages = [
        {"role": "system", "content": "You are a senior system architect."},
        {"role": "user", "content": prompt}
    ]
    
    payload = {
        "model": "ollama/llama3", # We request a generic model, the router decides
        "messages": messages,
        "temperature": 0.2
    }
    
    print("\n[Requesting Architecture Design]")
    print("Sending payload to Axon Proxy...")
    
    start_time = time.time()
    
    # We hit the proxy directly using TestClient
    response = client.post("/v1/chat/completions", json=payload)
    
    end_time = time.time()
    
    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        print(f"✅ Success! (Took {end_time - start_time:.2f} seconds)")
        print("\n--- LLM RESPONSE START ---")
        print(content)
        print("--- LLM RESPONSE END ---\n")
        
        # Verify Headers
        print("[Axon Headers]")
        for k, v in response.headers.items():
            if k.lower().startswith("x-axon"):
                print(f"  {k}: {v}")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")

if __name__ == "__main__":
    test_extreme_complexity()
