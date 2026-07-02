from tests.verify_llm_comprehension import highest_complexity_payload

from services.token_optimizer import TokenOptimizer

opt = TokenOptimizer()
result = opt.optimize({"role": "user", "content": highest_complexity_payload}, session_id="test_opt")
print(result.winner.strategy)
print(result.winner.token_estimate, "vs", result.json_baseline_tokens)
print(result.winner.savings_vs_json_pct)
