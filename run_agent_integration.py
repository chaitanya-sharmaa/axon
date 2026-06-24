import json
from openai import OpenAI

# 1. Point the standard OpenAI SDK to your local Axon Bridge
client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="your-api-key" # Put your real API key here!
)

def run_agent_loop():
    print("🤖 Starting Agent Integration Test...")
    print("Connecting to Axon Bridge at http://localhost:8080/v1\n")
    
    # We maintain a multi-turn conversation (which is heavy on tokens without Axon)
    messages = [
        {"role": "system", "content": "You are a helpful software engineering agent. You remember all context perfectly."}
    ]
    
    turns = [
        "Can you help me design a complex data pipeline in Python? Give me a huge initial spec.",
        "That looks good. Now, can you add a message queue (like RabbitMQ or Kafka) into that architecture and explain why?",
        "Perfect. Now write a fully detailed README for this exact project."
    ]

    for i, user_msg in enumerate(turns):
        print(f"=== TURN {i+1} ===")
        print(f"User: {user_msg}")
        messages.append({"role": "user", "content": user_msg})
        
        try:
            # We use .with_raw_response.create() so we can inspect the Axon custom headers!
            raw_response = client.chat.completions.with_raw_response.create(
                model="gemini/gemini-2.5-flash",
                messages=messages,
                temperature=0.7
            )
            
            # Extract standard response
            completion = raw_response.parse()
            assistant_msg = completion.choices[0].message.content
            messages.append({"role": "assistant", "content": assistant_msg})
            
            print(f"Agent (preview): {assistant_msg[:100]}...\n")
            
            # Read Axon's custom HTTP headers to see how much money the agent saved!
            headers = raw_response.headers
            if 'x-axon-savings-pct' in headers:
                print(f"🚀 AXON METRICS: You saved {headers.get('x-axon-savings-pct')}% tokens on this turn!")
                print(f"   Original Tokens: {headers.get('x-axon-original-tokens')}")
                print(f"   Billed Tokens: {headers.get('x-axon-billed-tokens')}")
                print(f"   Strategy Used: {headers.get('x-axon-strategy')}\n")
            else:
                print("⚠️ No Axon metrics found in headers. Did the request go through the proxy?\n")
                
        except Exception as e:
            print(f"❌ Error connecting to Agent: {e}")
            print("\nDid you remember to update 'your-api-key' in this script and use a valid model name for your provider?")
            break

if __name__ == "__main__":
    run_agent_loop()
