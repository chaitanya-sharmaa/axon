# Use Cases & Feature Examples

Axon Bridge is an agentic middleware that seamlessly intercepts LLM requests, optimizes them mathematically, and adds enterprise-grade resilience. Here are the primary ways to integrate and benefit from it.

---

## 1. The Universal Proxy Engine (LiteLLM Integration)

**Axon vs No Axon:**
| Without Axon | With Axon |
|---|---|
| You must rewrite your SDK code to support `openai`, `anthropic`, and `google-genai`. | **One SDK rules them all.** Send OpenAI-formatted payloads to Axon, and it translates them to 100+ providers automatically. |
| You pay full price for raw, bloated JSON token payloads. | Axon dynamically compresses your payload before it hits the provider, saving **~18% on every request** via structural compression. |

**How it works:**
Axon intercepts standard `/v1/chat/completions` requests. It compresses the `messages` array using its `TokenOptimizer`, and then uses its embedded LiteLLM engine to translate the payload and route it to the target LLM.

```python
import openai

# 1. Point the client to your local Axon Bridge
client = openai.OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="your-api-key",  # Pass ANY provider's API key
)

# 2. Seamlessly route to Gemini, Claude, or any 100+ model using OpenAI's SDK!
response = client.chat.completions.create(
    model="gemini/gemini-2.5-flash",  # Axon translates the payload automatically
    messages=[{"role": "user", "content": "Summarise the latest earnings report..."}],
    stream=True,
)

# Axon injects savings metrics into the HTTP response headers:
# x-axon-metrics: {"savings_pct": 18.0, "original_tokens": 15169, "compressed_tokens": 12440}
# x-axon-cost-saved-usd: 0.00156
```

---

## 2. Native Provider Prompt Caching (Anthropic & Gemini)

For maximum multi-turn savings without hallucinations, Axon uses **native provider-side caching** rather than proxy-level data deletion.

**How it works:**
- For **Anthropic (`claude-3`)**: Axon automatically marks the largest message and system prompt with `cache_control: ephemeral`. Anthropic's server caches the KV computation of those blocks and reuses it across turns — you are only billed for the new tokens.
- For **Gemini (paid plan)**: Enable `AXON_ENABLE_GEMINI_PROMPT_CACHE=true`. Axon injects the same hint via LiteLLM's Gemini adapter.

> [!IMPORTANT]
> Gemini Context Caching requires a **paid Gemini API plan**. Do **not** enable `AXON_ENABLE_GEMINI_PROMPT_CACHE` on free-tier keys — it will cause `429` errors.

```python
# No code changes needed — just set the env var and point at Axon:
# AXON_ENABLE_GEMINI_PROMPT_CACHE=true  (paid plan only)

client = openai.OpenAI(base_url="http://localhost:8080/v1", api_key="your-key")
response = client.chat.completions.create(
    model="claude-3-5-sonnet",
    messages=[
        {"role": "system", "content": "You are a data analyst."},
        {"role": "user", "content": very_large_context},  # <-- Axon auto-caches this
        {"role": "user", "content": "What is the average revenue?"},
    ]
)
# Turn 2+: Anthropic skips re-computing the large context — ~80% cost reduction.
```

---

## 3. Autonomous JSON Healing (Agentic Resilience)

**Axon vs No Axon:**
| Without Axon | With Axon |
|---|---|
| If the LLM generates a trailing comma or missing quote, your `json.loads()` crashes and your Agent dies. | Axon intercepts the `JSONDecodeError`, automatically appends the error to the message history, and asks the LLM to fix it *before* returning it to your Agent. |

```mermaid
sequenceDiagram
    participant Agent
    participant Axon
    participant LLM

    Agent->>Axon: Give me JSON data
    Axon->>LLM: Give me JSON data
    LLM-->>Axon: { "bad": "json", } (trailing comma)
    Note over Axon: JSONDecodeError Triggered!
    Axon->>LLM: The JSON was invalid. Fix this syntax error: trailing comma.
    LLM-->>Axon: { "bad": "json" } (fixed)
    Axon-->>Agent: { "bad": "json" } (Clean, valid response)
```

By adding `response_format={"type": "json_object"}`, Axon natively protects your pipelines from syntax crashes.

---

## 4. Streaming Circuit Breaker

**Axon vs No Axon:**
| Without Axon | With Axon |
|---|---|
| A rogue agent gets stuck in an infinite loop, streaming 100,000 tokens of gibberish and draining your API budget. | Pass `X-Axon-Max-Spend: 0.10` in the header. Axon counts tokens mid-stream. If the cost exceeds 10 cents, Axon gracefully terminates the TCP connection. |

```mermaid
graph LR
    LLM[Provider]:::llm -->|Streaming Data| Axon[Axon Proxy]:::axon
    Axon -->|Count Tokens| Calc{Check Budget}
    Calc -->|Under Budget| App[Client Agent]:::app
    Calc -->|Over Budget| Kill((Kill Connection!)):::error
    
    classDef llm fill:#059669,color:#fff
    classDef axon fill:#2563eb,color:#fff
    classDef app fill:#4f46e5,color:#fff
    classDef error fill:#ef4444,color:#fff
```

---

## 5. Native Python SDK Wrapper (`axon.patch`)

**Goal:** You want JSON Healing and token compression inside a local Python script without standing up a Docker container.

```python
import openai
from axon import patch

# Create a standard AsyncOpenAI client
client = openai.AsyncOpenAI(api_key="sk-your-real-key")

# Patch it with Axon
client = patch(client)

# Use it exactly as before. Axon intercepts the call locally!
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Huge payload..."}],
    response_format={"type": "json_object"}  # JSON Healing activated!
)
```

---

## 6. RAG and Vector DB Integration (LlamaIndex)

**Axon vs No Axon:**
| Without Axon | With Axon |
|---|---|
| You retrieve 10 large documents from a Vector DB. All 10 are sent to the LLM, burning 15k tokens. | Axon uses a fast, local BM25 `TokenOptimizer` post-processor. It scores the documents against the query, drops the irrelevant bottom 25%, and compresses the remaining 75%. You send fewer tokens instead of 15k. |

```python
from integrations.llamaindex import AxonNodePostprocessor
from services.token_optimizer import TokenOptimizer

# Configure the postprocessor
axon_postprocessor = AxonNodePostprocessor(
    optimizer=TokenOptimizer(), 
    model="gpt-4o",
    enable_pruning=True
)

# Apply it in your query engine
query_engine = index.as_query_engine(
    node_postprocessors=[axon_postprocessor]
)

response = query_engine.query("What is the Q3 revenue?")
```


---

