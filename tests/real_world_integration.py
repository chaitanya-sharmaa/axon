import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 1. We instantiate the STANDARD OpenAI Client
# But we point it to the local Axon Bridge (port 8000) instead of OpenAI's servers!
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "dummy"),
    base_url="http://127.0.0.1:8000/v1"
)

# 2. Let's create a realistic "Real World" Payload: A large block of Application Logs
# Imagine an agent pulling server logs to diagnose a problem.
# These logs are highly repetitive (same timestamp formats, same log levels, etc).
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

def run_real_world_scenario():
    print("🌍 REAL-WORLD INTEGRATION TEST")
    print("Sending 150 application logs to the LLM via standard OpenAI SDK...")
    
    # We ask the LLM to find the error in the logs.
    # Axon will transparently intercept this, compress it structurally, and forward it to Gemini.
    api_key = os.getenv("OPENAI_API_KEY", "dummy")
    target_model = "gemini/gemini-2.5-flash" if "AQ." in api_key else "gpt-4o-mini"
    
    response = client.chat.completions.create(
        model=target_model,
        messages=[
            {"role": "system", "content": "You are a DevOps assistant. Read the following JSON logs and identify any errors."},
            {"role": "user", "content": json.dumps(application_logs)},
            {"role": "user", "content": "Which job or shard failed?"}
        ],
        temperature=0.0
    )
    
    # The LLM's answer:
    answer = response.choices[0].message.content
    print("\n🤖 LLM Answer:")
    print(answer)
    print("-" * 50)
    
    # Axon Token Savings Metrics are injected directly into the response!
    # Because we are using the python openai client, we have to look at the raw HTTP response headers
    # if we want to see the exact savings. 
    # (In standard usage you'd see this on the Axon dashboard, but we can extract it for proof).
    # NOTE: In the v1 SDK, headers are accessible via the `response` object's hidden `_headers` if available,
    # but the easiest way to show proof is to hit the API with HTTPX directly just to print the headers.
    
    print("\n✅ The standard OpenAI SDK successfully parsed the response from the Axon Proxy.")

if __name__ == "__main__":
    run_real_world_scenario()

    print("\n--- Under the Hood (Raw HTTP request to show metrics) ---")
    import requests
    resp = requests.post(
        "http://127.0.0.1:8000/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}", "Content-Type": "application/json"},
        json={
            "model": "gemini/gemini-2.5-flash" if "AQ." in os.getenv("OPENAI_API_KEY", "") else "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a DevOps assistant. Read the following JSON logs and identify any errors."},
                {"role": "user", "content": json.dumps(application_logs)},
                {"role": "user", "content": "Which job or shard failed?"}
            ]
        }
    )
    metrics = json.loads(resp.headers.get("x-axon-metrics", "{}"))
    original = metrics.get("original_tokens")
    compressed = metrics.get("compressed_tokens")
    savings = metrics.get("savings_pct")
    print(f"Original Payload Tokens: {original}")
    print(f"Compressed Payload Sent to LLM: {compressed}")
    print(f"Net Savings: {savings}%")

