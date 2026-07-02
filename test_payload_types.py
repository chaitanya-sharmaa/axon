import asyncio
import json

from services.token_optimizer import TokenOptimizer


async def main():
    optimizer = TokenOptimizer()

    # Payload 1: Natural Language / Prompt
    natural_language = "Please write a story about a brave knight who fights a dragon in a dark cave." * 20

    # Payload 2: Massive JSON Log Array (often used in agent scratchpads)
    json_logs = json.dumps([
        {"timestamp": "2026-07-02T10:00:00Z", "level": "INFO", "message": "Agent started"},
        {"timestamp": "2026-07-02T10:00:01Z", "level": "DEBUG", "message": "Loaded config"},
        {"timestamp": "2026-07-02T10:00:02Z", "level": "ERROR", "message": "Failed to connect to DB"}
    ] * 20)

    # Payload 3: Agent Skill (Markdown Instructions)
    skill_markdown = """
# Data Analysis Skill
ALWAYS check for null values.
If nulls > 10%, drop the column.
    """ * 20

    payloads = {
        "Natural Language Prompt": {"role": "user", "content": natural_language},
        "JSON System Logs": {"role": "system", "content": json_logs},
        "Agent Skill (Markdown)": {"role": "system", "content": skill_markdown}
    }

    print("=== Axon Agnostic Payload Verification ===\n")

    for name, payload in payloads.items():
        print(f"Testing Payload Type: {name}")
        print(f"Original text length: {len(str(payload['content']))} chars")

        # Axon doesn't care what it is, it just optimizes it!
        result = optimizer.optimize(payload)

        print(f"Axon Winner Strategy: {result.winner.strategy}")
        print(f"Original Tokens: {result.json_baseline_tokens}")
        print(f"Optimized Tokens: {result.winner.token_estimate}")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
