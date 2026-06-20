import json
import uuid
from services.token_optimizer import TokenOptimizer

# --- SCENARIO 1: E-Commerce Product Catalog ---
catalog = []
for i in range(1, 101):
    catalog.append({
        "product_id": f"SKU-{1000+i}",
        "name": f"Smart Gadget Version {i}",
        "category": "Electronics" if i % 2 == 0 else "Home Goods",
        "price": 99.99 if i != 42 else 2499.99,
        "stock": 500,
        "specifications": {
            "weight_kg": 1.2 if i != 42 else 15.5,
            "dimensions": "10x10x5 cm",
            "warranty": "2 Years"
        },
        "description": "This is a premium smart gadget designed to make your life easier with AI-powered features." * 3
    })

# --- SCENARIO 2: Codebase Dependency Graph ---
ast_nodes = []
for i in range(1, 101):
    ast_nodes.append({
        "node_type": "ClassDef" if i % 5 == 0 else "FunctionDef",
        "name": f"DataProcessor_{i}" if i != 88 else "PaymentGatewayManager",
        "file_path": f"src/modules/processor_{i}.py",
        "author": "dev-team-alpha@company.com",
        "dependencies": [f"DataProcessor_{i-1}"] if i > 1 else [],
        "metadata": {"complexity": "O(N)", "test_coverage": "85%"}
    })
ast_nodes[87]["dependencies"] = ["StripeAPI", "UserDatabase", "SecurityLogger"]

# --- SCENARIO 3: Customer Support Chat Transcripts ---
chat_history = []
for i in range(1, 101):
    is_angry = (i == 37)
    chat_history.append({
        "timestamp": f"2026-06-15T10:{i%60:02d}:00Z",
        "sender_type": "Customer" if i % 2 != 0 else "Agent",
        "sender_id": f"usr_8832{i%5}",
        "channel": "WebChat_Portal_v2.1",
        "message_body": "I AM EXTREMELY FRUSTRATED MY ACCOUNT IS LOCKED!" if is_angry else f"Standard inquiry regarding order #{i*100}.",
        "sentiment_score": -0.9 if is_angry else 0.5
    })

def run_offline_scenario(name: str, payload: list):
    print(f"\n==================================================")
    print(f"🚀 SCENARIO: {name}")
    print(f"==================================================")
    
    # Instantiate Optimizer
    opt = TokenOptimizer()
    session_id = str(uuid.uuid4())
    
    baseline = len(json.dumps(payload)) // 4
    print(f"Baseline JSON Size: ~{baseline} tokens")
    
    # Turn 1: Cold Start (Structural Compression)
    res1 = opt.optimize({"role": "user", "content": payload}, session_id=session_id)
    print(f"\n[Turn 1: Initial Prompt]")
    print(f"Winning Algorithm: {res1.winner.strategy}")
    print(f"Tokens Actually Sent: {res1.winner.token_estimate} (Savings: {res1.winner.savings_vs_json_pct}%)")
    
    encoded_str = str(res1.winner.encoded)
    print("\n🔍 HOW AXON PRESERVED THE SEMANTICS (First 300 characters of compressed payload):")
    print(encoded_str[:300] + "...")
    
    # Turn 2: Follow-up question (TRON compression)
    res2 = opt.optimize({"role": "user", "content": payload}, session_id=session_id)
    print(f"\n[Turn 2: Follow-up Question]")
    print(f"Winning Algorithm: {res2.winner.strategy}")
    print(f"Tokens Actually Sent: {res2.winner.token_estimate} (Savings: {res2.winner.savings_vs_json_pct}%)")

if __name__ == "__main__":
    print("Testing 3 distinct, high-complexity real-world scenarios through the Axon Engine...\n")
    
    run_offline_scenario("E-Commerce Product Catalog (Nested Object Arrays)", catalog)
    run_offline_scenario("Codebase AST/Dependency Graph", ast_nodes)
    run_offline_scenario("Customer Support Chat Transcripts", chat_history)
