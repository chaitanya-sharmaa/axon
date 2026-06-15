# GCF Bridge Agent (Token-Saving Middleware)

This workspace includes a production-ready bridge layer that sits between any API/agent and your caller.

It accepts:
- JSON string input
- GCF string input (generic or graph)
- Python objects (dict/list/dataclass/pydantic-like)

It emits:
- GCF output (primary, 25-71% token savings)
- Optional JSON output (fallback compatibility)
- Estimated token savings (JSON vs GCF)
- Session-aware deduplication (70%+ savings on multi-turn)

## Files

- `app.py`: primary FastAPI entrypoint
- `gcf_fastapi.py`: backward-compatible entrypoint alias
- `core/app_config.py`: app wiring and singleton services
- `core/settings.py`: environment-driven configuration
- `services/bridge_service.py`: reusable GCF bridge with graph + generic support
- `services/sqlite_memory_store.py`: persistent SQLite-backed session storage
- `services/hybrid_memory.py`: multi-backend memory abstraction with Ruflo CLI/Python integration
- `services/security_policy.py`: domain allowlist + API key policy
- `domain/api_models.py`: API request/response models
- `domain/process_handlers.py`: payload processing handlers
- `api/routes/*_routes.py`: route modules grouped by concern
- `adapters/mcp_bridge_adapter.py`: MCP-style adapter helpers
- `examples/demo_usage.py`: runnable demo
- `examples/session_benchmark.py`: multi-turn benchmark
- `requirements.txt`: dependencies

## Install

```bash
python -m pip install -r requirements.txt
```

## Run Demo

```bash
python examples/demo_usage.py
```

## Run Middleware API

```bash
PYTHONPATH=/Users/chasharm4/Documents/gcf/bridge \
python -m uvicorn app:app --host 127.0.0.1 --port 8080
```

You can also run with env-configured host/port:

```bash
PYTHONPATH=/Users/chasharm4/Documents/gcf/bridge python app.py
```

## Configuration (Env Vars)

All major behavior is configurable via environment variables in `core/settings.py`.

- `GCF_APP_TITLE` (default: `GCF Bridge Middleware`)
- `GCF_APP_VERSION` (default: `0.3.0`)
- `GCF_APP_DESCRIPTION`
- `GCF_OPENAPI_DESCRIPTION`
- `GCF_OPENAPI_LOGO_URL`
- `GCF_HOST` (default: `127.0.0.1`)
- `GCF_PORT` (default: `8080`)
- `GCF_INCLUDE_JSON_FALLBACK` (`true|false`)
- `GCF_MEMORY_DB_PATH` (default: `/tmp/gcf_sessions.db`)
- `GCF_ENABLE_RUFLO_MEMORY` (`true|false`, default: `false`)
- `GCF_RUFLO_ENDPOINT` (optional endpoint when using Python client)
- `GCF_RUFLO_NAMESPACE` (default: `gcf-bridge`)
- `GCF_RUFLO_CLI_COMMAND` (default: `ruflo`)
- `GCF_RUFLO_PYTHON_MODULE` (default: `ruflo.memory`)
- `GCF_REQUIRE_API_KEY` (`true|false`)
- `GCF_ALLOW_ALL_DOMAINS` (`true|false`)
- `GCF_API_KEY`
- `GCF_ALLOWED_DOMAINS` (comma-separated list)
- `GCF_ROUTE_PREFIX_CORE` (default: empty)
- `GCF_ROUTE_PREFIX_PROCESS` (default: empty)
- `GCF_ROUTE_PREFIX_PROXY` (default: `/proxy`)
- `GCF_ROUTE_PREFIX_MEMORY` (default: `/memory`)
- `GCF_ROUTE_PREFIX_SECURITY` (default: `/security`)
- `GCF_ENABLE_CORE_ROUTES` (`true|false`)
- `GCF_ENABLE_PROCESS_ROUTES` (`true|false`)
- `GCF_ENABLE_PROXY_ROUTES` (`true|false`)
- `GCF_ENABLE_MEMORY_ROUTES` (`true|false`)
- `GCF_ENABLE_SECURITY_ROUTES` (`true|false`)

Example:

```bash
export GCF_API_KEY="prod-key-12345"
export GCF_REQUIRE_API_KEY=true
export GCF_ALLOWED_DOMAINS="api.github.com,httpbin.org"
export GCF_ROUTE_PREFIX_PROXY="/api/proxy"
export GCF_ENABLE_RUFLO_MEMORY=true
export GCF_RUFLO_CLI_COMMAND="ruflo"
export GCF_RUFLO_NAMESPACE="gcf-bridge"
```

### Core Endpoints (6)

- `GET /health` — status check
- `POST /translate/in` — normalize input to object
- `POST /translate/out` — convert output to GCF envelope
- `POST /process` — route through handler, return GCF (with graph auto-detection + session tracking)
- `POST /proxy/upstream` — forward HTTP request to upstream API
- `DELETE /memory/session/{session_id}` — clear session data and dedup cache

### Session Memory Endpoints (3)

- `GET /memory/sessions` — list all active sessions
- `GET /memory/session/{session_id}` — get session event history + cached symbols
- `DELETE /memory/cleanup` — remove sessions older than N days

### Security Endpoints (6)

- `GET /security/config` — view current security settings
- `POST /security/domain/allow?domain=...` — add domain to allowlist
- `DELETE /security/domain?domain=...` — remove domain from allowlist
- `POST /security/require-api-key?required=true|false` — toggle API key requirement
- `POST /security/allow-all-domains?allow=true|false` — enable unrestricted access (dev only)
- `GET /security/ruflo-status` — integration status for Ruflo backend

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
- Token savings per call
- Symbol schemas for deduplication tracking

**Ruflo Integration:** When `GCF_ENABLE_RUFLO_MEMORY=true`, process and proxy events are mirrored to Ruflo via Python client (`ruflo.memory`) or Ruflo CLI memory tools. The service falls back gracefully if Ruflo is unavailable.

Check runtime integration status:

```bash
curl http://127.0.0.1:8080/security/ruflo-status
```

## Security Features

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
export GCF_API_KEY="prod-key-12345"
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

Flexible symbol format (auto-converts to GCF):
- `name` + `module` → combined as qualified name
- `type` (class/function) → kind
- Optional: `docstring`, `params`, `returns`

Flexible edge format:
- `from`/`to` instead of `source`/`target`
- `type` (calls/references/etc.) instead of `edge_type`

## Multi-Turn Session Optimization

Run the benchmark to see cumulative savings across 10 calls in the same session:

```bash
python examples/session_benchmark.py
```

Example output (graph payloads):
```
Call  1: Symbols=15, Edges= 6 → GCF savings: 47.9%
Call  2: Symbols=18, Edges= 8 → GCF savings: 50.0%  (symbols cached)
Call  3: Symbols=21, Edges= 9 → GCF savings: 51.9%  (reusing refs)
...
Call 10: Symbols=42, Edges=20 → GCF savings: 52.1%
```

Per-call savings stabilize as repeated symbols get referenced, not re-encoded.

## Quick Integration

```python
from gcf_bridge_agent import GCFBridgeAgent

bridge = GCFBridgeAgent(include_json_fallback=True)

def my_agent(payload: dict) -> dict:
    return {"ok": True, "input": payload}

# Multi-turn: reuse same session_id across calls
envelope = bridge.process(inbound_data, my_agent, session_id="chat-123")

# send envelope["gcf"] to the next model hop
# keep envelope["json"] for legacy systems
```

## MCP-Style Adapter Example

```python
from mcp_adapter import GCFMCPAdapter

adapter = GCFMCPAdapter()

def tool_handler(payload: dict) -> dict:
    return {"received": payload, "ok": True}

result = adapter.invoke_tool(tool_handler, inbound_data, session_id="mcp-session-1")
```

## Architecture

```
Client API/Agent
        ↓
┌───────────────────────┐
│  GCF Bridge Middleware│
│  (FastAPI Service)    │
├───────────────────────┤
│ • Normalize input     │
│ • Route to handler    │
│ • Graph auto-detect   │
│ • Session dedup cache │
├───────────────────────┤
│ SecurityConfig        │
│ SessionMemoryStore    │
│ GCFBridgeAgent        │
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
