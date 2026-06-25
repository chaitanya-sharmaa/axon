import requests
import time

BASE_URL = "http://localhost:8080"
headers = {"Authorization": "Bearer test-key"}

def set_flag(flag, value):
    resp = requests.post(f"{BASE_URL}/admin/features", json={flag: value})
    print(f"Set {flag} to {value}: {resp.status_code}")

def test_routing():
    print("\n--- Testing Semantic Routing ---")
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Write a complex react application using Redux and TypeScript."}]
    }
    
    # Disabled
    set_flag("enable_semantic_routing", False)
    r1 = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, headers=headers).json()
    model_disabled = r1.get("model")
    print(f"When disabled, model used: {model_disabled} (Expected: gpt-4o-mini)")
    
    # Enabled
    set_flag("enable_semantic_routing", True)
    r2 = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, headers=headers).json()
    model_enabled = r2.get("model")
    print(f"When enabled, model used: {model_enabled} (Expected: gpt-4o)")

def test_tool_compression():
    print("\n--- Testing Tool Compression ---")
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
        "tools": [{"type": "function", "function": {"name": "get_weather", "description": "Get weather", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}}}]
    }
    
    # Disabled
    set_flag("enable_tool_compression", False)
    r1 = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, headers=headers)
    print(f"When disabled, X-Axon-Savings-Pct header: {r1.headers.get('X-Axon-Savings-Pct')} (Expected: 0.0 or None)")
    
    # Enabled
    set_flag("enable_tool_compression", True)
    r2 = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, headers=headers)
    print(f"When enabled, X-Axon-Savings-Pct header: {r2.headers.get('X-Axon-Savings-Pct')} (Expected: > 0)")


def test_semantic_cache():
    print("\n--- Testing Exact Match Cache ---")
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "What is the capital of France? (Test UUID: cache123)"}]
    }
    
    # Prime the cache
    set_flag("enable_exact_match_cache", True)
    requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, headers=headers)
    time.sleep(1)
    
    # Disabled (Should miss cache and hit OpenAI)
    set_flag("enable_exact_match_cache", False)
    r1 = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, headers=headers)
    print(f"When disabled, X-Axon-Savings-Pct header: {r1.headers.get('X-Axon-Savings-Pct')} (Expected: Not 100.0)")
    
    # Enabled (Should hit cache)
    set_flag("enable_exact_match_cache", True)
    r2 = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, headers=headers)
    print(f"When enabled, X-Axon-Savings-Pct header: {r2.headers.get('X-Axon-Savings-Pct')} (Expected: 100.0)")

try:
    test_routing()
    test_tool_compression()
    test_semantic_cache()
except Exception as e:
    print("Error during tests:", e)
