# Use Cases & Examples

Axon Bridge is designed to fit into your existing stack with as little friction as possible. Here are the primary ways to integrate it, ordered from easiest to most advanced.

---

## 1. The Drop-in OpenAI Proxy (Zero Code Changes)

**Goal:** You have an existing application using the official `openai` SDK (or any compatible client like LiteLLM) and want to cut costs immediately without rewriting your logic.

**How it works:** Axon provides a fully compatible `/v1/chat/completions` endpoint. It intercepts your messages, compresses them using the cheapest strategy, forwards them to the real OpenAI API, and returns the standard response.

**Example:**

```python
import openai

# 1. Point the client to your local Axon Bridge
client = openai.OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="your-openai-api-key", # Axon securely forwards this
)

# 2. Use the SDK exactly as normal
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Summarise the latest earnings report..."}],
    stream=True, # Streaming is fully supported!
)

# Axon injects savings metrics into the HTTP response headers:
# x-axon-metrics: {"savings_pct": 38.2, "original_tokens": 812, "compressed_tokens": 501}
# x-axon-cost-saved-usd: 0.00156
```

---

## 2. LangChain Integration

**Goal:** You use LangChain to orchestrate your LLM calls and want automatic token compression across your entire chain.

**How it works:** Install the `langchain` extra (`pip install "axon-bridge[langchain]"`). Add the `AxonCallbackHandler` to your LLM instantiation. The handler hooks into the LLM lifecycle to compress prompts right before they hit the network.

**Example:**

```python
from langchain_openai import ChatOpenAI
from integrations.langchain import AxonCallbackHandler
from services.token_optimizer import TokenOptimizer

# Initialize the callback handler
handler = AxonCallbackHandler(optimizer=TokenOptimizer(), session_id="my-session")

# Attach it to your LLM
llm = ChatOpenAI(model="gpt-4o", callbacks=[handler])

# Run your chain
llm.invoke("Explain the transformer architecture...")

print(handler.last_savings)
# {'savings_pct': 42.1, 'original_tokens': 620, 'compressed_tokens': 359}
```

---

## 3. Compress an Existing API (`/proxy/upstream`)

**Goal:** You have an existing internal API or microservice that returns large JSON payloads. You want to pass that data to an LLM, but want it compressed first.

**How it works:** Instead of your agent calling the API directly, it calls Axon's `/proxy/upstream` endpoint. Axon fetches the JSON from your API, compresses it, and returns the compact string ready for your LLM.

**Example:**

```bash
curl -X POST http://127.0.0.1:8080/proxy/upstream \
  -H "Content-Type: application/json" \
  -d '{
    "upstream_url": "https://api.your-company.com/customer/123/history",
    "method": "GET",
    "session_id": "chat-session-42"
  }'
```

Response includes the compressed text in `compact_text` and the full token savings in `metrics`.

---

## 4. Python Library (Direct Usage)

**Goal:** You are building a custom Python agent framework and want granular control over when and how data is compressed.

**How it works:** Import `AxonService` and `TokenOptimizer` directly into your code.

**Example:**

```python
from services.bridge_service import AxonService
from services.token_optimizer import TokenOptimizer

axon = AxonService(token_optimizer=TokenOptimizer())

def my_agent_tool(user_id: str) -> dict:
    # ... complex logic returning a large dict ...
    return {"user_id": user_id, "history": [...]}

# Compress the output before returning it to the LLM
envelope = axon.convert_output(
    my_agent_tool("u123"), 
    session_id="session-42"
)

print(f"Send this to LLM: {envelope['compact_text']}")
```

---

## 5. Batch Processing

**Goal:** You need to pre-process or compress a large dataset of JSON payloads offline (e.g., preparing data for fine-tuning or bulk analysis).

**How it works:** Send an array of requests to the `POST /batch` endpoint. Axon processes them concurrently and returns all compressed strings in one round-trip.

**Example:**

```bash
curl -X POST http://localhost:8080/batch \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "requests": [
      {"payload": {"user": "alice", "action": "login"}, "session_id": "s1"},
      {"payload": {"user": "bob",   "action": "view"},  "session_id": "s2"}
    ]
  }'
```

---

## 6. Multi-Agent Orchestration

**Goal:** You have a "swarm" of specific tool-agents (e.g., a "code-analyzer" and a "text-summarizer") and want a central router to dispatch payloads to the right agent and compress the result.

**How it works:** Register your agents with Axon's orchestrator, then use `/agent/dispatch` (route to best match), `/agent/parallel` (run specific agents concurrently), or `/agent/swarm` (fan-out to all).

**Example (Dispatch):**

```bash
# Send a payload and ask for an agent with the "graph" capability.
curl -X POST http://127.0.0.1:8080/agent/dispatch \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "symbols": [{"qualified_name": "api.Service", "kind": "class"}]
    },
    "capability": "graph"
  }'
```