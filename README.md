# Axon: The AI Token-Saving Bridge

**Axon** is a smart middleware layer that sits between your application and Large Language Models (LLMs) to dramatically reduce API costs and improve response speed.

It automatically intercepts your data payloads, benchmarks multiple advanced compression formats (like TOON and TRON), and sends the most token-efficient version to the LLM—**saving you up to 70% on tokens**.

## Why Axon?

In the brain, an **axon** is a nerve fiber that transmits information efficiently. This library acts as a digital axon for your AI systems, connecting your services and optimizing the data that flows between them. It ensures every payload is transmitted in the most compact and efficient form possible.

## Key Benefits

*   💰 **Drastic Cost Reduction**: Automatically finds the cheapest data format for every call, significantly cutting your LLM API bills.
*   ⚡️ **Increased Speed & Performance**: Fewer tokens mean faster processing by the LLM, leading to quicker API responses and a snappier user experience.
*   🧠 **Expanded Context Window**: Fit up to 4x more data into the same context window, enabling more capable and knowledgeable agents.
*   🔌 **Effortless Integration**: Start saving tokens in minutes. Use it as a simple proxy for existing APIs with **zero code changes** or as a library in your Python code.

## How It Works

Axon acts as a "last-mile" translation layer right before the LLM. It intelligently compresses outgoing data and decompresses incoming data, keeping your internal systems clean.

```
[ Your Application / Agent ]
             |
    (Sends standard JSON)
             |
             ▼
    ┌────────────────────┐
    │     Axon Bridge    │
    │ (Middleware Layer) │
    ├────────────────────┤
    │ 1. Intercepts JSON │
    │ 2. Benchmarks TOON,│
    │    TRON, GCF, etc. │
    │ 3. Selects cheapest│
    │    format.         │
    └────────────────────┘
             |
    (Sends compressed text)
             |
             ▼
       [ LLM API ]
 (e.g., OpenAI, Anthropic)
```

## Getting Started in 3 Steps

### Step 1: Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 2: Run the Axon Server

From the project root directory, start the FastAPI server.

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8080 --reload
```

### Step 3: Integrate with Your Application

You have two primary options for integration:

#### Option A: Proxy an Existing API (Easiest)

This method requires **no code changes** to your existing services. Simply tell Axon to call your API, and it will handle the compression of the response.

Send a `POST` request to Axon's `/proxy/upstream` endpoint:

```bash
curl -X POST http://127.0.0.1:8080/proxy/upstream \
  -H "Content-Type: application/json" \
  -d '{
    "upstream_url": "https://api.your-service.com/get-data",
    "method": "GET",
    "session_id": "user-session-123"
  }'
```

Axon returns a token-optimized payload, ready for the LLM.

#### Option B: Use as a Python Library

For more control, import `AxonService` directly into your Python code to wrap agent functions.

```python
from services.bridge_service import AxonService

axon = AxonService()

def my_agent_function(payload: dict) -> dict:
    # Your agent's logic here...
    return {"status": "complete", "result": payload["input"] * 2}

# Wrap the function call with Axon
inbound_data = {"input": 123}
envelope = axon.process(inbound_data, my_agent_function, session_id="agent-session-456")

# `envelope["compact_text"]` contains the compressed output for the LLM
print(envelope["compact_text"])
print(f"Saved {envelope['metrics']['estimated_savings_percent']}% tokens!")
```

## Files

- `app.py`: primary FastAPI entrypoint
- `core/app_config.py`: app wiring and singleton services
- `core/settings.py`: environment-driven configuration
- `services/bridge_service.py`: reusable token-saving bridge with graph + generic support
- `services/sqlite_memory_store.py`: persistent SQLite-backed session storage
- `services/security_policy.py`: domain allowlist + API key policy
- `domain/api_models.py`: API request/response models
- `domain/process_handlers.py`: payload processing handlers
- `api/routes/*_routes.py`: route modules grouped by concern
- `adapters/mcp_bridge_adapter.py`: MCP-style adapter helpers
- `examples/demo_usage.py`: runnable demo
- `examples/session_benchmark.py`: multi-turn benchmark
- `examples/strategy_benchmark.py`: latency benchmark for each encoding strategy
- `requirements.txt`: dependencies

## Install
*(See "Getting Started" above for installation and run commands)*

## Configuration (Env Vars)

All major behavior is configurable via environment variables in `core/settings.py`.

- `AXON_APP_TITLE` (default: `Axon Token Bridge`)
- `AXON_APP_VERSION` (default: `0.3.0`)
- `AXON_APP_DESCRIPTION`
- `AXON_OPENAPI_DESCRIPTION`
- `AXON_OPENAPI_LOGO_URL`
- `AXON_HOST` (default: `127.0.0.1`)
- `AXON_PORT` (default: `8080`)
- `AXON_INCLUDE_JSON_FALLBACK` (`true|false`)
- `AXON_MEMORY_DB_PATH` (default: `/tmp/axon_sessions.db`)
- `AXON_REQUIRE_API_KEY` (`true|false`)
- `AXON_ALLOW_ALL_DOMAINS` (`true|false`)
- `AXON_API_KEY`
- `AXON_ALLOWED_DOMAINS` (comma-separated list)
- `AXON_ROUTE_PREFIX_CORE` (default: empty)
- `AXON_ROUTE_PREFIX_PROCESS` (default: empty)
- `AXON_ROUTE_PREFIX_PROXY` (default: `/proxy`)
- `AXON_ROUTE_PREFIX_MEMORY` (default: `/memory`)
- `AXON_ROUTE_PREFIX_SECURITY` (default: `/security`)
- `AXON_ENABLE_CORE_ROUTES` (`true|false`)
- `AXON_ENABLE_PROCESS_ROUTES` (`true|false`)
- `AXON_ENABLE_PROXY_ROUTES` (`true|false`)
- `AXON_ENABLE_MEMORY_ROUTES` (`true|false`)
- `AXON_ENABLE_SECURITY_ROUTES` (`true|false`)

Example:

```bash
export AXON_API_KEY="prod-key-12345"
export AXON_REQUIRE_API_KEY=true
export AXON_ALLOWED_DOMAINS="api.github.com,httpbin.org"
export AXON_ROUTE_PREFIX_PROXY="/api/proxy"
```

## Upstream Proxy Example

Use the middleware as a pass-through to any external API, then return GCF output to your model layer:

```bash
curl -sS http://127.0.0.1:8080/proxy/upstream \
  -H 'content-type: application/json' \
  -d '{
    "upstream_url": "https://httpbin.org/post",
    "method": "POST",
    "session_id": "chat-42",
    "data": {
      "tenant": "acme",
      "query": "show active services"
    }
  }'
```

Response contains:
- `gcf`: compact wire payload for model hops
- `json`: optional fallback object
- `metrics`: estimated token savings
- `upstream`: status and content-type metadata

## Session Memory & Persistence

Persistent SQLite-backed memory tracks sessions, cached symbols, and event history:

```bash
# List all active sessions
curl http://127.0.0.1:8080/memory/sessions

# Get session details and event history
curl http://127.0.0.1:8080/memory/session/chat-42?limit=50

# Clean up sessions older than 7 days
curl -X DELETE http://127.0.0.1:8080/memory/cleanup?days=7
```

Memory automatically logs:
- Process calls and handlers invoked
- Upstream proxy calls and response status

## Reference: Security & Configuration

### Domain Allowlist

The `/proxy/upstream` endpoint enforces a domain allowlist by default:

```bash
# Current config shows allowed domains
curl http://127.0.0.1:8080/security/config

# Add domain to allowlist
curl -X POST "http://127.0.0.1:8080/security/domain/allow?domain=api.stripe.com"

# Remove domain
curl -X DELETE "http://127.0.0.1:8080/security/domain?domain=api.stripe.com"
```

Default allowlist:
- `httpbin.org`, `api.github.com`, `api.example.com`, `localhost`, `127.0.0.1`

### API Key Authentication

Enable optional API key validation on proxy requests:

```bash
# Enable API key requirement
curl -X POST "http://127.0.0.1:8080/security/require-api-key?required=true"

# Then all proxy requests MUST include X-API-Key header
curl -X POST "http://127.0.0.1:8080/proxy/upstream" \
  -H "X-API-Key: your-secret-key" \
  -H "content-type: application/json" \
  -d '{"upstream_url": "https://httpbin.org/post", "method": "POST"}'
```

To set a specific API key in code:

```python
from core.app_config import security_config

security_config.api_key = "prod-key-12345"
security_config.require_api_key = True
```

Or via environment variable:

```bash
export AXON_API_KEY="prod-key-12345"
```

### Unrestricted Mode (Dev Only)

For development/testing without domain restrictions:

```bash
curl -X POST "http://127.0.0.1:8080/security/allow-all-domains?allow=true"
```

**WARNING:** Only use in trusted, isolated environments.

## Graph Profile Auto-Detection

If your payload contains a `symbols` key, the bridge automatically uses the **graph profile** instead of generic encoding:

```json
{
  "symbols": [
    {"name": "ServiceA", "module": "api", "type": "class"},
    {"name": "ServiceB", "module": "api", "type": "class"}
  ],
  "edges": [
    {"from": "ServiceA", "to": "ServiceB", "type": "calls"}
  ]
}
```

## API Endpoint Reference

### Agent Orchestration

- `GET /agent/list`: Lists all registered agents and their capabilities.
- `POST /agent/dispatch`: Routes a payload to the single best agent based on a requested `capability` or `agent_name`.
- `POST /agent/parallel`: Dispatches a payload to multiple agents concurrently, one for each specified `capability`.
- `POST /agent/swarm`: Fans out a payload to all registered agents in parallel.

### Proxy

- `POST /proxy/upstream`: Forwards a request to any external API and compresses its response. This is the easiest way to integrate Axon.

### Processing & Translation

- `POST /process`: Runs a payload through a built-in handler function (e.g., `echo`) and returns the compressed *input* payload. Useful for testing compression strategies.
- `POST /translate/in`: A utility to decode any format (JSON, GCF) into a standard Python object.
- `POST /translate/out`: A utility to encode a Python object into the Axon envelope with compression metrics.

### Session Memory

- `GET /memory/sessions`: Lists all active sessions being tracked.
- `GET /memory/session/{session_id}`: Retrieves the event history and cached data for a specific session.
- `DELETE /memory/session/{session_id}`: Deletes all data for a specific session.
- `DELETE /memory/cleanup`: A maintenance endpoint to purge old sessions.

### Security

- `GET /security/config`: Shows the current security settings (e.g., domain allowlist).
- `POST /security/domain/allow`: Adds a new domain to the proxy's allowlist.
- `DELETE /security/domain`: Removes a domain from the proxy's allowlist.
- `POST /security/require-api-key`: Toggles whether the proxy endpoint requires an API key.

## Contributing

Contributions are welcome! Please feel free to submit a pull request.

## License

This project is licensed under the MIT License.

## Architecture

```
Client API/Agent
        ↓
┌───────────────────────┐
│  Axon Bridge          │
│  (FastAPI Service)    │
├───────────────────────┤
│ • Normalize input     │
│ • Route to handler    │
│ • Graph auto-detect   │
│ • Session dedup cache │
├───────────────────────┤_
│ SecurityConfig        │
│ SessionMemoryStore    │
│ AxonService           │
└───────────────────────┘
        ↓
    GCF Output
  (25-71% savings)
```

## Performance Notes

- **Small payloads** (<10 items): JSON often smaller (overhead not amortized)
- **Medium payloads** (10-100 items): GCF ~25-30% savings
- **Large payloads** (100+ items): GCF ~45-50% savings
- **Multi-turn sessions**: 70%+ cumulative savings by call 5 (graph dedup)

Use GCF for:
- Agent-to-agent communication
- Long-running stateful sessions
- Context-heavy workflows

Keep JSON for:
- One-off API calls
- Public APIs (compatibility)
- Client-side consumption

## Notes on Saving More Tokens

1. Keep field names short in upstream payloads.
2. Chunk very large arrays before sending to the model.
3. Reuse stable IDs in your app-level protocol for repeated objects.
4. Always pass `session_id` on repeated, graph-heavy interactions.
