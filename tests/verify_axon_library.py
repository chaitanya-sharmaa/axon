import json
from services.token_optimizer import TokenOptimizer
from tests.verify_llm_comprehension import highest_complexity_payload

def run_axon_library_test():
    print("🧠 Axon Library Standalone Verification")
    print("---------------------------------------")
    print("This tests the core TokenOptimizer completely offline, independently of any LLM.")
    print("We will simulate a 3-turn conversation where the payload doesn't change.\n")
    
    # Instantiate the optimizer directly
    opt = TokenOptimizer()
    session_id = "standalone-axon-session"
    
    # Provide the baseline json size for comparison
    json_baseline = len(json.dumps(highest_complexity_payload, separators=(",", ":")))
    
    for turn in range(1, 4):
        print(f"--- Turn {turn} ---")
        # Run Axon Optimization
        result = opt.optimize(
            {"role": "user", "content": highest_complexity_payload}, 
            session_id=session_id
        )
        
        strategy = result.winner.strategy
        tokens = result.winner.token_estimate
        baseline = result.json_baseline_tokens
        savings = result.winner.savings_vs_json_pct
        
        print(f"🏆 Winning Algorithm: {strategy}")
        print(f"📊 Tokens: {tokens} (Baseline: {baseline}) -> {savings}% Savings")
        
        # Show a snippet of the actual encoded payload that would be sent to the LLM!
        encoded_snippet = str(result.winner.encoded)[:100].replace('\n', ' ')
        if len(str(result.winner.encoded)) > 100:
            encoded_snippet += "..."
        print(f"📦 Encoded Payload Snippet: {encoded_snippet}\n")


if __name__ == "__main__":
    run_axon_library_test()
