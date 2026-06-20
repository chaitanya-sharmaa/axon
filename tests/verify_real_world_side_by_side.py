import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# We instantiate the Axon Bridge Client
axon_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="http://127.0.0.1:8000/v1"
)

api_key = os.getenv("OPENAI_API_KEY", "")

# Create the 150 Application Logs Payload
application_logs = []
for i in range(1, 151):
    status = "ERROR" if i == 73 else "INFO"
    message = f"Database connection timeout on shard {i % 4}" if i == 73 else f"Processed background job {i} successfully."
    application_logs.append({
        "timestamp": "2026-06-20T14:00:00Z",
        "service": "billing-api-worker",
        "level": status,
        "region": "us-east-1",
        "container_id": f"cnt-8x92j-{i % 10}",
        "message": message
    })

def run_baseline_uncompressed():
    print("--- 🔴 UNCOMPRESSED BASELINE (Direct to LLM) ---")
    
    # We bypass Axon completely and hit Gemini directly
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": "You are a DevOps assistant. Read the following JSON logs and identify any errors.\n" + json.dumps(application_logs) + "\nCan you tell me which job or shard failed?"}]}
        ],
        "generationConfig": {"temperature": 0.0}
    }
    
    import time
    while True:
        resp = requests.post(url, json=payload)
        data = resp.json()
        
        if "candidates" in data and len(data["candidates"]) > 0:
            answer = data["candidates"][0]["content"]["parts"][0]["text"]
            print("🤖 LLM Answer:\n" + answer.strip())
            break
        elif data.get("error", {}).get("code") == 429:
            print("Hit rate limit, waiting 10s...")
            time.sleep(10)
        else:
            print("Error getting answer:", data)
            break

def run_axon_compressed():
    print("\n--- 🟢 AXON COMPRESSED (Through Proxy) ---")
    
    # We send the exact same payload through Axon Proxy
    response = axon_client.chat.completions.create(
        model="gemini/gemini-2.5-flash" if "AQ." in api_key else "gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a DevOps assistant. Read the following JSON logs and identify any errors."},
            {"role": "user", "content": json.dumps(application_logs)},
            {"role": "user", "content": "Can you tell me which job or shard failed?"}
        ],
        temperature=0.0
    )
    
    print("🤖 LLM Answer:\n" + response.choices[0].message.content.strip())
    
    # To prove savings happened under the hood, let's print the metrics
    resp_metrics = requests.post(
        "http://127.0.0.1:8000/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gemini/gemini-2.5-flash" if "AQ." in api_key else "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a DevOps assistant. Read the following JSON logs and identify any errors."},
                {"role": "user", "content": json.dumps(application_logs)},
                {"role": "user", "content": "Can you tell me which job or shard failed?"}
            ]
        }
    )
    metrics = json.loads(resp_metrics.headers.get("x-axon-metrics", "{}"))
    print("\n📊 Axon Compression Metrics:")
    print(f"Original Tokens: {metrics.get('original_tokens')}")
    print(f"Tokens Sent: {metrics.get('compressed_tokens')} ({metrics.get('savings_pct')}% Savings)")

if __name__ == "__main__":
    run_baseline_uncompressed()
    run_axon_compressed()
