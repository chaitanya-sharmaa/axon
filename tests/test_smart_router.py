import os
import sys

# Ensure we can import from the app root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.intent_classifier import classify_intent
from services.smart_router import route_model

def run_ml_router_tests():
    print("\n🚀 STARTING AXON ML SEMANTIC ROUTER TEST 🚀\n")
    
    # 1. Casual Chat -> Should route to 'low' (lite models)
    prompt1 = "Hey, what's up? Can you tell me a funny story?"
    intent1 = classify_intent(prompt1)
    model1 = route_model("gpt-4o", 20, prompt1)
    
    print(f"[1] Casual Chat Prompt: '{prompt1}'")
    print(f"    Classified Intent: {intent1}")
    print(f"    Routed Model: {model1}")
    assert intent1 == "low", "Casual chat should be classified as low complexity"
    assert "mini" in model1.lower(), "Casual chat should route to lite model (gpt-4o-mini)"
    
    # 2. Code Generation -> Should route to 'high' (pro models)
    prompt2 = "I need to write a Python script that parses a CSV file and calculates the standard deviation."
    intent2 = classify_intent(prompt2)
    model2 = route_model("claude-3-5-sonnet-20241022", 50, prompt2)
    
    print(f"\n[2] Code Gen Prompt: '{prompt2}'")
    print(f"    Classified Intent: {intent2}")
    print(f"    Routed Model: {model2}")
    assert intent2 == "high", "Code generation should be classified as high complexity"
    assert "sonnet" in model2.lower(), "Code gen should route to pro model (claude-3-5-sonnet)"
    
    # 3. Complex Reasoning -> Should route to 'high' (pro models)
    prompt3 = "Please evaluate the following legal indemnity clause and list out potential edge cases."
    intent3 = classify_intent(prompt3)
    model3 = route_model("gemini/gemini-2.5-flash", 100, prompt3)
    
    print(f"\n[3] Reasoning Prompt: '{prompt3}'")
    print(f"    Classified Intent: {intent3}")
    print(f"    Routed Model: {model3}")
    assert intent3 == "high", "Legal reasoning should be classified as high complexity"
    assert "pro" in model3.lower(), "Legal reasoning should route to pro model (gemini-2.5-pro)"

    print("\n✅ All assertions passed! ML Semantic Intent Classifier accurately routes requests!")

if __name__ == "__main__":
    run_ml_router_tests()
