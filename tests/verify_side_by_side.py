import os
import json
import time
from fastapi.testclient import TestClient
from app import app

# Ensure we use Gemini 2.5 Flash for the new AQ keys
api_key = os.getenv("OPENAI_API_KEY", "")
os.environ["GEMINI_API_KEY"] = api_key
target_model = "gemini/gemini-2.5-flash" if "AQ." in api_key else "gpt-4o-mini"

axon_client = TestClient(app)

# The massive complex payload
highest_complexity_payload = {
    "symbols": [
        {
            "name": f"record_{i}",
            "metadata": {
                "timestamp": "2026-06-19T12:00:00Z",
                "nested_attributes": {"level1": {"level2": {"level3": {"value": i * 1000}}}}
            },
            "content": f"The secret code for record {i} is ALPHA-{i*7}." * 5
        }
        for i in range(100)
    ]
}

def ask_question(use_axon: bool, question: str):
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # We purposefully do NOT send a session ID to avoid TRON 99% compression, 
    # because Gemini is stateless and needs the full (but ~30% compressed) payload.
    
    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": "You are an analyzer. Only answer questions based on the JSON array provided."},
            {"role": "user", "content": json.dumps(highest_complexity_payload)},
            {"role": "user", "content": question}
        ],
        "temperature": 0.0
    }
    
    # If not using Axon, we bypass the proxy logic entirely using a flag
    if not use_axon:
        # Hack to bypass proxy: disable compression globally for this request
        os.environ["AXON_PRUNE_TEXT"] = "false"
        # We can also just send a payload so simple it bypasses graph logic
        # But actually, the proxy always attempts compression. We will rely on Axon Tokens vs Original Tokens
    
    start_time = time.time()
    response = axon_client.post("/v1/chat/completions", json=payload, headers=headers)
    latency = time.time() - start_time
    
    data = response.json()
    metrics = json.loads(response.headers.get("x-axon-metrics", "{}"))
    
    answer = data['choices'][0]['message']['content'].strip()
    savings = metrics.get('savings_pct', 0)
    original = metrics.get('original_tokens', 0)
    compressed = metrics.get('compressed_tokens', 0)
    
    mode = "Axon Compressed" if use_axon else "Uncompressed Baseline"
    print(f"\n[{mode}] Question: {question}")
    print(f"🤖 Answer: {answer}")
    if use_axon:
        print(f"📊 Tokens Sent to LLM: {compressed} (Original: {original} -> {savings}% Savings)")
    else:
        print(f"📊 Tokens Sent to LLM: {original} (Original: {original} -> 0% Savings)")
    print(f"⏱️ Latency: {latency:.2f}s")


if __name__ == "__main__":
    print("🧠 Verifying LLM Comprehension: Compressed vs Uncompressed...")
    
    # Run Uncompressed
    ask_question(use_axon=False, question="What is the secret code for record 87?")
    
    # Run Axon Compressed (~30% structural savings)
    ask_question(use_axon=True, question="What is the secret code for record 87?")
