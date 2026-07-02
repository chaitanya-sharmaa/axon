import json
import os
import time

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import app

load_dotenv()

client = TestClient(app)

def create_massive_payload():
    items = []
    # 100 complex items to mimic an active agent scraping a catalog or fetching DB rows
    for i in range(100):
        items.append({
            "product_id": f"SKU-{1000+i}",
            "name": f"Enterprise Flux Capacitor Model {i}",
            "description": "A highly advanced multi-dimensional tool for resolving temporal paradoxes.",
            "price": 1000.0 + (i * 15),
            "stock": 50 - (i % 10),
            "specifications": {
                "weight": f"{1.5 + (i * 0.1)}kg",
                "dimensions": {"width": "10cm", "height": "15cm", "depth": "20cm"},
                "material": "Unobtanium alloy",
                "power_source": "Plutonium reaction / Lightning"
            },
            "reviews": [
                {"user": "DocB", "rating": 5, "comment": "Great Scott! This thing really works. Highly recommended."},
                {"user": "MartyM", "rating": 4, "comment": "Heavy. But it gets the job done."}
            ]
        })
    return items

def run_multiturn_test():
    payload = create_massive_payload()
    json_payload_str = json.dumps(payload)
    print("==================================================")
    print("🤖 STARTING REAL-WORLD MULTI-TURN AGENT SIMULATION")
    print("==================================================")

    api_key = os.getenv("OPENAI_API_KEY")
    session_id = "real_world_agent_session_001"

    # Base system context (persists across turns)
    messages = [
        {"role": "system", "content": "You are a helpful data analyst. Read the following e-commerce catalog data and answer the user's questions."},
        {"role": "user", "content": json_payload_str}
    ]

    # 3 Real-World Agent Turns
    turns = [
        "Turn 1 (Cold Start): Identify the product_id of the cheapest item.",
        "Turn 2 (Follow-up): Are there any products made of 'Unobtanium alloy'?",
        "Turn 3 (Reasoning): What is the average stock of the first 5 items?"
    ]

    total_original = 0
    total_compressed = 0
    total_saved = 0

    for i, question in enumerate(turns, 1):
        print(f"\n[Turn {i}] Agent asks: '{question}'")
        messages.append({"role": "user", "content": question})

        req_body = {
            "model": "ollama/llama3",
            "messages": messages,
            "temperature": 0.0
        }

        start_time = time.time()

        response = client.post(
            "/v1/chat/completions",
            json=req_body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Axon-Session-ID": session_id # Critical for TRON Session Deduplication!
            }
        )
        latency = time.time() - start_time

        if response.status_code != 200:
            print(f"  ❌ Error: {response.status_code} - {response.text}")
            return

        metrics = response.headers.get("x-axon-metrics")
        data = response.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if metrics:
            m = json.loads(metrics)
            orig = m.get('original_tokens', 0)
            comp = m.get('compressed_tokens', 0)
            sav_pct = m.get('savings_pct', 0)
            strat = m.get('best_strategy', 'Unknown')

            total_original += orig
            total_compressed += comp

            print(f"  ✓ Tokens: {orig} raw -> {comp} compressed ({sav_pct:.2f}% saved) [Strategy: {strat}] [Latency: {latency:.2f}s]")
            print(f"  ✓ LLM Answer:\n{answer}\n")

        # Append assistant response to maintain conversation history
        messages.append({"role": "assistant", "content": answer})
        time.sleep(1) # Slight pause to simulate thinking

    print("\n==================================================")
    print("📈 FINAL MULTI-TURN METRICS (Overall Savings)")
    print("==================================================")
    print(f"Total Tokens if you used raw JSON:  {total_original}")
    print(f"Total Tokens actually sent to API: {total_compressed}")

    overall_saved_pct = (1 - (total_compressed / total_original)) * 100
    print(f"\n✨ OVERALL SAVINGS: {overall_saved_pct:.2f}% ✨")
    print(f"You avoided paying for {total_original - total_compressed} redundant structural tokens!")

if __name__ == "__main__":
    run_multiturn_test()
