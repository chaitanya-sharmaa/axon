# Core Concepts

Understanding how Axon Bridge achieves massive token savings requires looking at three core concepts: dynamic encoding, multi-turn deduplication, and model-aware pricing.

---

## 1. Dynamic Encoding (The "Optimizer")

JSON is notoriously token-heavy due to extensive punctuation (`"`, `{`, `}`, `,`), repeated keys, and whitespace. 

Instead of relying on a single compression format, Axon's `TokenOptimizer` takes every inbound JSON payload and **benchmarks it against 8 different encoding strategies simultaneously**. It estimates the token count for each format using the target LLM's specific tokenizer (e.g., `tiktoken` for OpenAI, Anthropic's API for Claude), and automatically selects the cheapest one.

Strategies include:
- **`graph`**: A highly compact format optimized for code context (symbols, ASTs, call graphs).
- **`generic`**: A dense `key=value` string format that strips out JSON punctuation.
- **`schema_values`**: Strips keys entirely. Sends a schema map once, then only comma-separated values.
- **`json`**: The standard baseline (retained if it somehow happens to be the cheapest).

---

## 2. Multi-Turn Session Deduplication (TOON & TRON)

The most dramatic token savings (up to 70%+) occur during multi-turn LLM conversations. When an agent or user continuously polls an API or receives updated context, they often re-send 90% of the same data. 

Axon solves this by maintaining **stateful sessions** (backed by SQLite or Redis). If you pass a `session_id` in your requests, Axon unlocks advanced stateful strategies:

*   **TOON (Token-Oriented Object Notation - "Deltas")**: Axon compares the current payload to the previous turn and sends *only the fields that changed*. 
    *   *Strategies: `generic_delta`, `graph_delta`*
*   **TRON (Token-Reduced Object Notation - "References")**: Axon remembers previously seen long strings or objects and replaces them with tiny references (e.g., `@1`) on subsequent turns.
    *   *Strategies: `generic_session`, `graph_session`*

---

## 3. Real Dollar Cost Tracking

Engineers care about tokens, but businesses care about dollars.

Axon includes a built-in pricing database (`services/pricing.py`) that maps models (like `gpt-4o` or `claude-3-5-sonnet`) to their exact input/output costs per 1,000 tokens. 

Whenever you specify a `model` in your request (or use the OpenAI-compatible proxy, which passes the model automatically), Axon calculates the actual **USD cost saved** by the compression. This is returned in the API responses or injected into HTTP headers (`x-axon-cost-saved-usd`).

---

## 4. Persistent Memory Store

To support TOON and TRON, Axon must remember what it sent to the LLM previously. This state is managed by the `MemoryStore`.

*   **SQLite (Default)**: Best for local development or single-container deployments. Uses Write-Ahead Logging (WAL) for high concurrency.
*   **Redis**: Designed for enterprise and Kubernetes. Allows you to run multiple Axon Bridge replicas behind a load balancer that all share the same session memory.

Axon includes LRU (Least Recently Used) eviction mechanisms (`AXON_MAX_SESSIONS`) to ensure this memory never grows unbounded.

---

## 5. The Plugin Registry

Axon is extensible by design. If you have a highly specific data format (e.g., a proprietary binary log format you want to compress to hex), you don't need to fork the repo. 

You can use the `@register_strategy` decorator in your own Python code to inject custom compression algorithms directly into Axon's `TokenOptimizer`. Axon will benchmark your custom strategy alongside its built-in ones.