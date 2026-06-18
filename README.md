# Axon Bridge

**Token-efficient middleware for LLM APIs.** Axon sits between your application and any LLM, automatically benchmarks 8 encoding strategies, and sends the cheapest one — saving **up to 70% on API tokens** with zero changes to your existing code.

**Original Author:** [Chaitanya Sharma](https://github.com/chaitanya-sharmaa/axon)

```
pip install axon-bridge
axon serve
```

> **Drop-in OpenAI proxy.** Point any OpenAI SDK client at Axon instead of `api.openai.com` and get instant token savings with one line changed.

---

## Why Axon?

| Problem | Axon's solution |
|---|---|
| LLM API bills are high | Auto-picks the cheapest encoding per call — Axon, TOON (delta), TRON (session), schema-values |
| Sessions re-send the same data | Multi-turn deduplication: only changed fields are transmitted after turn 1 |
| Hard to observe token usage | Every response includes savings %, token counts, and optional dollar cost |
| Integrating a new tool takes work | Drop-in OpenAI-compatible `/v1/chat/completions` proxy — change one URL |
| Complex deployment | Single Docker image, SQLite default, Redis for horizontal scale |

### Benchmarks

Here is an live benchmark showing Axon's estimated token savings versus a raw JSON baseline for various payload types. Note how **multi-turn session deduplication** drastically increases token savings in large repeated payloads (e.g., *Large List (5 turns)*).

```mermaid
xychart-beta
    title "Axon Token Savings vs JSON Baseline"
    x-axis ["Small JSON", "Nested JSON", "Graph Payload", "Large List (5 turns)"]
    y-axis "Savings (%)" 0 --> 100
    bar [25.0, 0.0, 3.85, 59.68]
```

---

## Quickstart

### Option 1 — Docker (recommended)

```bash
docker compose up
# Server is live at http://localhost:8080
```

### Option 2 — pip install

```bash
pip install axon-bridge
axon serve --port 8080
```

### Option 3 — local dev

```bash
git clone https://github.com/chaitanya-sharmaa/axon.git
cd axon/bridge
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload
```

---

## Zero-Code Integration — OpenAI Proxy

The fastest way to start saving tokens. Change **one line** in your existing code:

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8080/v1",   # ← only change
    api_key="any-value",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Summarise the latest earnings report..."}],
)

# Token savings are in the response header:
# x-axon-metrics: {"savings_pct": 38.2, "original_tokens": 812, "compressed_tokens": 501}
# x-axon-cost-saved-usd: 0.00156
```

Axon compresses your `messages[]`, forwards to the real OpenAI API, and returns the standard response. Streaming (`stream=True`) is fully supported.

---

## Python Library Usage

```python
from services.bridge_service import AxonService
from services.token_optimizer import TokenOptimizer

axon = AxonService(token_optimizer=TokenOptimizer())

# Compress any payload
envelope = axon.convert_output(
    {"user": "alice", "role": "admin", "org": "acme", "plan": "enterprise"},
    session_id="session-42",
)

print(envelope["compact_text"])
# → user=alice,role=admin,org=acme,plan=enterprise

print(envelope["metrics"]["estimated_savings_percent"])
# → 31.4

# Turn 2 — same session, same values → TRON deduplication kicks in
envelope2 = axon.convert_output(
    {"user": "alice", "role": "admin", "org": "acme", "plan": "enterprise", "region": "eu-west-2"},
    session_id="session-42",
)
print(envelope2["compact_text"])
# → region=eu-west-2  (only the new field!)
```

---

## LangChain Integration

```python
from langchain_openai import ChatOpenAI
from integrations.langchain import AxonCallbackHandler
from services.token_optimizer import TokenOptimizer

handler = AxonCallbackHandler(optimizer=TokenOptimizer(), session_id="my-session")
llm = ChatOpenAI(model="gpt-4o", callbacks=[handler])

llm.invoke("Explain the transformer architecture...")

print(handler.last_savings)
# {'savings_pct': 42.1, 'original_tokens': 620, 'compressed_tokens': 359}
```

---

## CLI

```bash
# Start the server
axon serve --port 8080 --reload

# Benchmark all strategies against a JSON file
axon benchmark my_payload.json --model gpt-4o

# One-shot compress a JSON string
axon encode '{"symbols": [{"qualified_name": "pkg.Auth", "kind": "class"}]}'

# Show model pricing table
axon pricing

# Inspect / delete a session
axon session show my-session-id
axon session clear my-session-id --yes
```

---

## Batch Processing

Compress multiple payloads in a single HTTP call:

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

## Encoding Strategies

Axon benchmarks all enabled strategies on every call and picks the winner:

| Strategy | Best for | Mechanism |
|---|---|---|
| `graph` | Code context (symbols + edges) | Axon compact graph format |
| `graph_delta` | Repeated graph calls | Only sends added/removed symbols (TOON) |
| `graph_session` | Long graph sessions | References previously sent symbols by index (TRON) |
| `generic` | Flat key-value dicts | Compact `key=value` text |
| `generic_delta` | Repeated generic calls | Only sends changed fields (TOON) |
| `generic_session` | Long generic sessions | References repeated values by key (TRON) |
| `schema_values` | Tabular data, same keys | Sends schema once, then values only |
| `json` | Baseline / compatibility | Raw JSON (always available as fallback) |

**Performance benchmarks:**

| Payload size | Savings (first turn) | Savings (session, turn 5+) |
|---|---|---|
| Small (<10 fields) | 10–25% | 40–60% |
| Medium (10–50 fields) | 25–40% | 55–70% |
| Large graph (100+ symbols) | 40–55% | 65–75% |

---

## API Reference

### OpenAI-Compatible
| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/models` | List available models |
| `POST` | `/v1/chat/completions` | Chat completions with compression (streaming supported) |
| `POST` | `/v1/embeddings` | Embeddings proxy |

### Core
| Method | Path | Description |
|---|---|---|
| `GET` | `/health/live` | Liveness probe (always 200 if process running) |
| `GET` | `/health/ready` | Readiness probe (503 if DB unavailable) |
| `POST` | `/translate/in` | Decode any format to Python object |
| `POST` | `/translate/out` | Encode object to Axon envelope |

### Processing
| Method | Path | Description |
|---|---|---|
| `POST` | `/process` | Run payload through a handler and compress result |
| `POST` | `/batch` | Compress multiple payloads concurrently |

### Proxy
| Method | Path | Description |
|---|---|---|
| `POST` | `/proxy/upstream` | Forward request to any external API and compress response |

### Agents
| Method | Path | Description |
|---|---|---|
| `GET` | `/agent/list` | List registered agents |
| `POST` | `/agent/dispatch` | Route to best agent by capability |
| `POST` | `/agent/parallel` | Dispatch to multiple agents concurrently |
| `POST` | `/agent/swarm` | Fan-out to all agents |

### Memory
| Method | Path | Description |
|---|---|---|
| `GET` | `/memory/sessions` | List active sessions |
| `GET` | `/memory/session/{id}` | Get session history |
| `DELETE` | `/memory/session/{id}` | Delete session |
| `DELETE` | `/memory/cleanup` | Purge sessions older than N days |

### Security
| Method | Path | Description |
|---|---|---|
| `GET` | `/security/config` | Current security settings |
| `POST` | `/security/domain/allow` | Add domain to allowlist |
| `DELETE` | `/security/domain` | Remove domain from allowlist |
| `POST` | `/security/require-api-key` | Toggle API key enforcement |

---

## Configuration

Copy `.env.example` to `.env` and set what you need. Every value has a sensible default.

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `AXON_PORT` | `8080` | Server port |
| `AXON_LOG_FORMAT` | `text` | `text` or `json` (for Datadog/Splunk) |
| `AXON_MEMORY_TYPE` | `sqlite` | `sqlite` or `redis` |
| `AXON_MAX_SESSIONS` | `1000` | LRU cap for in-memory session state |
| `AXON_REQUIRE_API_KEY` | `false` | Enforce `X-API-Key` on proxy requests |
| `AXON_ALLOWED_DOMAINS` | *(see .env.example)* | Comma-separated proxy allowlist |
| `OPENAI_API_KEY` | — | Forwarded to OpenAI when using `/v1/` routes |
| `AXON_ENABLE_OPENAI_ROUTES` | `true` | Toggle `/v1/` endpoints |
| `AXON_RATE_LIMIT_PROXY` | `60/minute` | Rate limit for proxy endpoint |

---

## Deployment

### Docker

```bash
# SQLite (single instance)
docker compose up

# Redis (multi-instance / horizontal scale)
docker compose -f docker-compose.yml -f docker-compose.redis.yml up
```

### Kubernetes

The `/health/live` and `/health/ready` endpoints map directly to liveness and readiness probes:

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
```

---

## Project Structure

```
bridge/
├── app.py                      # FastAPI entrypoint
├── cli.py                      # axon CLI (typer)
├── pyproject.toml              # Package metadata & build config
├── requirements.txt            # Runtime dependencies
├── Dockerfile
├── docker-compose.yml          # SQLite mode
├── docker-compose.redis.yml    # Redis override
├── .env.example                # All AXON_* variables documented
├── CHANGELOG.md
├── CONTRIBUTING.md
│
├── api/
│   ├── middleware/
│   │   └── request_id.py       # X-Request-ID propagation
│   └── routes/
│       ├── core_routes.py      # /health/live, /health/ready, /translate/*
│       ├── v1_openai_routes.py # /v1/chat/completions, /v1/models
│       ├── batch_routes.py     # /batch
│       ├── proxy_routes.py     # /proxy/upstream
│       ├── agent_routes.py     # /agent/*
│       ├── memory_routes.py    # /memory/*
│       ├── process_routes.py   # /process
│       └── security_routes.py  # /security/*
│
├── core/
│   ├── app_config.py           # Singleton service wiring
│   ├── logging_config.py       # Structured JSON logging
│   └── settings.py             # Env-driven config (dotenv)
│
├── services/
│   ├── token_optimizer.py      # Core: benchmarks all 8 strategies
│   ├── bridge_service.py       # AxonService public API
│   ├── payload_cache.py        # LRU cache (skip re-encoding identical payloads)
│   ├── pricing.py              # Model pricing → dollar savings
│   ├── plugin_registry.py      # @register_strategy plugin system
│   ├── sqlite_memory_store.py  # Persistent SQLite session store (WAL mode)
│   ├── redis_memory_store.py   # Redis session store
│   ├── memory_store.py         # BaseMemoryStore ABC
│   ├── security_policy.py      # API key + domain allowlist
│   ├── agent_orchestrator.py   # Multi-agent dispatch/swarm
│   └── tokenizer_factory.py    # tiktoken / Anthropic tokenizer
│
├── integrations/
│   └── langchain.py            # AxonCallbackHandler for LangChain
│
├── adapters/
│   └── mcp_bridge_adapter.py   # MCP-style tool I/O adapter
│
├── domain/
│   ├── api_models.py           # Pydantic request/response models
│   └── process_handlers.py     # Built-in payload handlers
│
├── examples/
│   ├── demo_usage.py           # Live end-to-end demo
│   ├── session_benchmark.py    # Multi-turn savings benchmark
│   └── strategy_benchmark.py  # Per-strategy latency benchmark
│
├── docs/
│   ├── 01-use-cases.md
│   └── 03-core-concepts.md
│
└── tests/
    ├── conftest.py
    └── test_token_optimizer.py
```

---

## Custom Encoding Strategies (Plugin System)

```python
from services.plugin_registry import register_strategy
from typing import Any

@register_strategy("my_strategy")
def encode_my_way(obj: Any, session_id: str | None = None) -> str:
    # your compression logic
    return compressed_text

# Now use it:
from services.token_optimizer import TokenOptimizer
optimizer = TokenOptimizer(enabled_strategies=["generic", "my_strategy", "json"])
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, test commands, and how to add a strategy.

```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check .
```

---

## License

Apache 2.0 — see `LICENSE`.
