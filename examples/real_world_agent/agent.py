import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

print("=== Starting Real-World Agent Integration ===")

# 1. Initialize the standard OpenAI Client
# We trick it into using the Axon Bridge running on localhost!
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY", "dummy"),
    base_url="http://localhost:8000/v1"
)

# 2. Simulate an Agent Payload (e.g. a RAG pipeline or Code Analyzer)
# This simulates sending a large context window of code symbols to the LLM.
print("\n[Agent] Constructing large architecture payload...")
payload = {
    "symbols": [
        {"name": f"CoreSystem_Module_{i}", "kind": "class", "score": 1.0} for i in range(150)
    ],
    "edges": [
        {"source": f"CoreSystem_Module_{i}", "target": f"CoreSystem_Module_{i+1}", "type": "depends_on"} for i in range(149)
    ],
    "tool": "code_architecture_analyzer",
    "token_budget": 2000
}

# In a normal app, you'd serialize this to JSON and send it to OpenAI
prompt_content = json.dumps(payload)
print(f"[Agent] Raw JSON prompt length: {len(prompt_content)} characters.")

# 3. Call the LLM through the Axon Bridge
# We use `.with_raw_response` so we can inspect the custom HTTP headers Axon returns.
print("[Agent] Sending request to OpenAI (routed through Axon Bridge proxy)...")

try:
    raw_response = client.chat.completions.with_raw_response.create(
        model="gemini/gemini-2.5-flash",
        messages=[
            {
                "role": "system", 
                "content": "You are a code architect. Briefly summarize the structure of the provided module dependency graph in 2 sentences."
            },
            {
                "role": "user", 
                "content": prompt_content
            }
        ],
        temperature=0.7
    )
    
    # Parse standard response
    parsed = raw_response.parse()
    
    print("\n=== Upstream LLM Response ===")
    print(parsed.choices[0].message.content)
    
    print("\n=== Axon Bridge Savings (Extracted from HTTP Headers) ===")
    metrics_header = raw_response.headers.get("x-axon-metrics")
    saved_usd = raw_response.headers.get("x-axon-cost-saved-usd")
    
    if metrics_header:
        print(f"Token Savings: {metrics_header}")
    if saved_usd:
        print(f"Estimated Cost Saved: ${saved_usd}")
        
except Exception as e:
    print(f"\n[Error] Failed to communicate with LLM: {e}")
    print("Please ensure you have exported OPENAI_API_KEY in your terminal.")
