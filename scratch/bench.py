from services.token_optimizer import TokenOptimizer
from typing import Any
import json
import uuid
import litellm

def run():
    products = []
    for i in range(100):
        products.append({
            "product_id": f"SKU-{1000+i}",
            "name": f"Product {i}",
            "price": 19.99 + i,
            "category": "Electronics" if i % 2 == 0 else "Home",
            "stock": 100 - i,
            "specs": {"weight": "1kg", "color": "blue"},
            "description": "This is a great product that you should definitely buy.",
            "rating": 4.5
        })
    
    base_json = json.dumps(products)
    base_tokens = len(litellm.encode(model="gpt-4o", text=base_json))
    print(f"Base tokens: {base_tokens}")

    opt = TokenOptimizer(enabled_strategies=["generic_delta", "json"]) # ENABLE TOON
    sess_id = str(uuid.uuid4())
    
    # Turn 1
    res1 = opt.optimize({"products": products}, sess_id)
    print(f"Turn 1 Strategy: {res1.winner.strategy}")
    print(f"Turn 1 Tokens: {res1.winner.token_estimate} (vs {base_tokens})")
    print(f"Turn 1 Savings: {100 - (res1.winner.token_estimate/base_tokens)*100:.2f}%")

    # Turn 2
    res2 = opt.optimize({"products": products}, sess_id)
    print(f"Turn 2 Strategy: {res2.winner.strategy}")
    print(f"Turn 2 Tokens: {res2.winner.token_estimate} (vs {base_tokens})")
    print(f"Turn 2 Savings: {100 - (res2.winner.token_estimate/base_tokens)*100:.2f}%")

run()
