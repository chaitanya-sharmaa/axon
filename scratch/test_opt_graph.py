from services.token_optimizer import TokenOptimizer
from tests.verify_llm_comprehension import highest_complexity_payload

opt = TokenOptimizer()
result1 = opt.optimize({"role": "user", "content": highest_complexity_payload}, session_id="test_graph")
print("Turn 1:", result1.winner.strategy, result1.winner.savings_vs_json_pct)

result2 = opt.optimize({"role": "user", "content": highest_complexity_payload}, session_id="test_graph")
print("Turn 2:", result2.winner.strategy, result2.winner.savings_vs_json_pct)
