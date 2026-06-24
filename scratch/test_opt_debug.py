import json
import asyncio
from services.token_optimizer import TokenOptimizer
from tests.verify_llm_comprehension import highest_complexity_payload

opt = TokenOptimizer(enabled_strategies=["generic"])
result = opt.optimize({"role": "user", "content": highest_complexity_payload}, session_id="test_opt")
print("Winner:", result.winner.strategy)
print("Winner Tokens:", result.winner.token_estimate, "vs", result.json_baseline_tokens)
print("Winner savings:", result.winner.savings_vs_json_pct)
