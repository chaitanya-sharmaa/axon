import asyncio

from services.text_pruner import prune_text
from services.token_optimizer import TokenOptimizer

# Sample Skill Text (Duplicated to make it large enough to trigger any size thresholds)
SKILL_TEXT = """
# Data Analysis Skill
## Description
This skill outlines the process for analyzing datasets, checking for null values, and generating reports.

## Instructions
1. Load the data using pandas.
2. ALWAYS check for null values. If nulls > 10%, drop the column.
3. Compute the mean and median for all numeric columns.
4. Output the final result in Markdown table format.

## Edge Cases
- If the dataset is empty, return an error message immediately.
- If the file is not CSV, attempt to parse it as JSON.
""" * 50

async def main():
    print("--- Original Text ---")
    print(f"Original Length: {len(SKILL_TEXT)} chars\n")

    # 1. Test Pruning (what Axon uses for large text blocks if enabled)
    pruned_text = prune_text(SKILL_TEXT)
    print("--- After Text Pruner ---")
    print(f"Pruned Length: {len(pruned_text)} chars\n")

    # 2. Test Structural Optimizer
    optimizer = TokenOptimizer()
    payload = {"role": "system", "content": pruned_text}
    result = optimizer.optimize(payload)

    print("--- Structural Optimizer ---")
    print(f"Winner Strategy: {result.winner.strategy}")
    print(f"Baseline Tokens (JSON): {result.json_baseline_tokens}")
    print(f"Optimized Tokens: {result.winner.token_estimate}")
    print(f"Savings %: {result.winner.savings_vs_json_pct}%\n")

    with open("compressed_skill_test.txt", "w", encoding="utf-8") as f:
        f.write(result.winner.encoded)

    print("Wrote compressed output to 'compressed_skill_test.txt'.")

if __name__ == "__main__":
    asyncio.run(main())
