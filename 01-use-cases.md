# Use Cases & Examples

Here are step-by-step examples for the most common integration patterns.

## Scenario 1: Compress an Existing API's Response (Easiest)

*   **Goal:** You have an existing API that returns JSON, and you want to compress its output for an LLM **without changing your API's code.**
*   **Endpoint to use:** `POST /proxy/upstream`

Axon will call your API, get the response, and automatically return the most token-efficient version.

**Example:**

```bash
# Tell Axon to call your API endpoint and compress the result.
curl -X POST http://127.0.0.1:8080/proxy/upstream \
  -H "Content-Type: application/json" \
  -d '{
    "upstream_url": "https://api.your-service.com/get-data",
    "method": "GET",
    "session_id": "user-session-123"
  }'
```

The response will contain the compressed payload in the `gcf` field, ready to be sent to your LLM.

---

## Scenario 2: Route a Task to the Best-Suited Agent

*   **Goal:** You have a "swarm" of agents with different skills (e.g., a "code-analyzer" and a "text-summarizer") and you need to send a payload to the right one.
*   **Endpoint to use:** `POST /agent/dispatch`

Axon's orchestrator will look at the `capability` you request and route the payload to the highest-priority agent that can handle it.

**Example:**

```bash
# Send a code-related payload and ask for an agent with the "graph" capability.
curl -X POST http://127.0.0.1:8080/agent/dispatch \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "symbols": [{"qualified_name": "api.Service", "kind": "class"}]
    },
    "capability": "graph",
    "session_id": "dev-session-abc"
  }'
```

Axon will automatically route this to the `graph_agent`, run it, and return the compressed result.

---

## Scenario 3: Get Input from Multiple Agents at Once

*   **Goal:** You want to run the same data through multiple agents simultaneously to get different analyses (e.g., linting and documentation generation).
*   **Endpoint to use:** `POST /agent/parallel`

Axon will run all requested capabilities concurrently and return a list of results.

**Example:**

```bash
# Ask for both "graph" and "active_items" analysis on the same payload.
curl -X POST http://127.0.0.1:8080/agent/parallel \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {"items": [{"id":1, "status":"active"}]},
    "capabilities": ["graph", "active_items"],
    "session_id": "multi-task-xyz"
  }'
```

---

## Scenario 4: Use as a Python Library

*   **Goal:** You are building a Python agent and want to compress the output of a function directly in your code.
*   **Method:** Import and use the `AxonService` class.

This gives you full control within your application.

**Example:**

```python
from services.bridge_service import AxonService

axon = AxonService()

def my_agent_function(payload: dict) -> dict:
    # Your agent's logic here...
    return {"status": "complete", "result": payload["input"] * 2}

# Axon normalizes input, runs your handler, and compresses the output.
envelope = axon.process({"input": 123}, my_agent_function)

# `envelope["gcf"]` contains the compressed output for the LLM.
print(f"Compressed output: {envelope['gcf']}")
print(f"Saved {envelope['metrics']['estimated_savings_percent']:.1f}% tokens!")
```