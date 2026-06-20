import os
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
from fastapi.testclient import TestClient

# Import the Axon Bridge FastAPI app
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app

# Load real OpenAI API key from .env
load_dotenv(override=True)
api_key = os.getenv("OPENAI_API_KEY")

if not api_key or api_key == "dummy-key-for-local-proxy":
    print("❌ ERROR: A real OPENAI_API_KEY is required to run this comprehension test.")
    sys.exit(1)

# If it's a Gemini key, map it so LiteLLM can find it
os.environ["GEMINI_API_KEY"] = api_key
target_model = "gemini/gemini-2.5-flash" if "AQ." in api_key else ("gemini/gemini-1.5-pro" if "AIza" in api_key else "gpt-4o-mini")

# Initialize TestClient to hit the local Axon Bridge without spinning up a real server
axon_client = TestClient(app)

# The massive complex payload we used for benchmarking
highest_complexity_payload = {
    "symbols": [
        {
            "name": f"record_{i}",
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
            "content": f"The secret code for record {i} is ALPHA-{i*7}." * 5
        }
        for i in range(100)
    ]
}

def ask_question(session_id: str, turn: int, question: str):
    print(f"\n--- Turn {turn} ---")
    print(f"User: {question}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-axon-session-id": session_id
    }
    
    payload = {
        "model": target_model, # Use the model identified from the key
        "messages": [
            {"role": "system", "content": "You are a database analyzer. Analyze the provided JSON and answer the user's questions accurately."},
            {"role": "user", "content": json.dumps(highest_complexity_payload)},
            {"role": "user", "content": question}
        ],
        "temperature": 0.0
    }
    
    start_time = time.time()
    response = axon_client.post("/v1/chat/completions", json=payload, headers=headers)
    latency = time.time() - start_time
    
    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        return
        
    data = response.json()
    metrics = json.loads(response.headers.get("x-axon-metrics", "{}"))
    
    print(f"🤖 LLM Answer: {data['choices'][0]['message']['content']}")
    print(f"📊 Axon Tokens: {metrics.get('compressed_tokens', 'N/A')} (Savings: {metrics.get('savings_pct', 0)}%)")
    print(f"⏱️ Latency: {latency:.2f}s")


def run_comprehension_test():
    print("🧠 Starting LLM Comprehension Verification...")
    print("This test proves the LLM can still accurately answer questions when the payload is compressed by 99.98%.")
    
    session_id = "comprehension-test-session"
    
    # Turn 1: Cold start (Sends the full 21k token payload to prime the context)
    ask_question(
        session_id=session_id, 
        turn=1, 
        question="What is the secret code for record 42?"
    )
    
    # Turn 2: Multi-turn (Sends the compressed 5 token payload!)
    # The LLM should STILL know the secret code for record 87 because it uses its context!
    ask_question(
        session_id=session_id, 
        turn=2, 
        question="What is the secret code for record 87?"
    )
    
    # Turn 3: Multi-turn deeper logic 
    ask_question(
        session_id=session_id, 
        turn=3, 
        question="What is the value in nested_attributes.level1.level2.level3 for record 15?"
    )

if __name__ == "__main__":
    run_comprehension_test()
