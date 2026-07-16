# API & Configuration Reference

Axon Bridge is configured entirely through **environment variables** (loaded from `.env` or your container runtime). All settings are powered by **Pydantic V2 `BaseSettings`** — misconfigured values fail loudly at startup with a `ValidationError` rather than silently defaulting.

> **Convention:** Every variable follows the `AXON_` prefix pattern. Comma-separated string fields (`AXON_ENABLED_FORMATS`, `AXON_ALLOWED_DOMAINS`) are automatically split into lists.

---

## ⚡ Quick-Reference Cheat Sheet

The fastest way to find what you need. All variables at a glance:

| Variable | Default | On by default? |
|---|---|---|
| `AXON_HOST` | `127.0.0.1` | — |
| `AXON_PORT` | `8080` | — |
| `AXON_ENV` | `development` | — |
| `AXON_OPENAI_API_KEY` | *(none)* | — |
| `AXON_OPENAI_BASE_URL` | *(none)* | — |
| `AXON_ADMIN_API_KEY` | *(none)* | — |
| `AXON_LOG_FORMAT` | `text` | — |
| `AXON_LOG_LEVEL` | `INFO` | — |
| `AXON_MEMORY_TYPE` | `turso` | — |
| `AXON_TURSO_URL` | `file:./axon_sessions.db` | — |
| `AXON_TURSO_AUTH_TOKEN` | *(none)* | — |
| `AXON_REDIS_URL` | `redis://localhost:6379/0` | — |
| `AXON_TOKENIZER_MODEL` | `cl100k_base` | — |
| `AXON_ENABLED_FORMATS` | *(all 8)* | — |
| `AXON_MAX_SESSIONS` | `1000` | — |
| `AXON_ALLOWED_DOMAINS` | *(default list)* | — |
| `AXON_ALLOW_ALL_DOMAINS` | `false` | — |
| `AXON_REQUIRE_API_KEY` | `false` | — |
| `AXON_CORS_ORIGINS` | *(none)* | — |
| `AXON_ENABLE_EXACT_MATCH_CACHE` | `true` | ✅ |
| `AXON_ENABLE_SEMANTIC_CACHE` | `true` | ✅ |
| `AXON_ENABLE_TOOL_COMPRESSION` | `true` | ✅ |
| `AXON_ENABLE_VISION_OPTIMIZER` | `true` | ✅ |
| `AXON_ENABLE_AGENTIC_OPTIMIZATIONS` | `true` | ✅ |
| `AXON_ENABLE_AGENTIC_SCHEMA_DIFF` | `true` | ✅ |
| `AXON_ENABLE_AGENTIC_SCRATCHPAD` | `true` | ✅ |
| `AXON_ENABLE_AGENTIC_OBSERVATION_WINDOW` | `true` | ✅ |
| `AXON_ENABLE_AGENTIC_LOOP_DETECTION` | `true` | ✅ |
| `AXON_CORS_ORIGINS` | *(none)* | ❌ opt-in |
| `AXON_ENABLE_SEMANTIC_ROUTING` | `false` | ❌ opt-in |
| `AXON_ENABLE_RAG_CONTEXT` | `false` | ❌ opt-in |
| `AXON_ENABLE_PROMPT_FIREWALL` | `false` | ❌ opt-in |
| `AXON_ENABLE_PII_REDACTION` | `false` | ❌ opt-in |
| `AXON_ENABLE_HALLUCINATION_GUARD` | `false` | ❌ opt-in |
| `AXON_ENABLE_FACT_EXTRACTION` | `false` | ❌ opt-in |
| `AXON_ENABLE_LLMLINGUA_COMPRESSION` | `false` | ❌ opt-in |
| `AXON_ENABLE_ASSISTANTS_ROUTES` | `false` | ❌ opt-in |
| `AXON_ENABLE_AGENT_ROUTES` | `false` | ❌ opt-in |
| `AXON_ENABLE_TENANT_QUOTAS` | `false` | ❌ opt-in |
| `AXON_ENABLE_GEMINI_PROMPT_CACHE` | `false` | ❌ opt-in |

---

## ⚙️ Configuration Deep-Dive

### 1. Core Server

| Variable | Default | Description |
|---|---|---|
| `AXON_HOST` | `127.0.0.1` | Bind address. Set `0.0.0.0` to expose on your network or inside Docker. |
| `AXON_PORT` | `8080` | Listen port. Must be a valid integer — Pydantic will raise `ValidationError` on invalid input. |
| `AXON_ENV` | `development` | Set to `production` to enforce `AXON_ADMIN_API_KEY`. Startup will fail if the key is missing in production mode. |
| `AXON_APP_TITLE` | `Axon Token Bridge` | Title shown in the OpenAPI `/docs` UI. |
| `AXON_APP_VERSION` | `0.3.0` | Version string shown in `/health` response and OpenAPI docs. |
| `AXON_OPENAI_API_KEY` | *(none)* | The upstream LLM key forwarded to providers. If unset, clients must supply their own key via the standard `Authorization: Bearer` header (BYOK mode). |
| `AXON_OPENAI_BASE_URL` | *(none)* | Default upstream base URL (e.g. `https://api.groq.com/openai/v1`). If unset, clients can supply per-request via `X-Upstream-Base-Url` header. |

### 2. Logging

| Variable | Default | Description |
|---|---|---|
| `AXON_LOG_FORMAT` | `text` | `text` for human-readable output (development), `json` for structured logs (production / log aggregation). |
| `AXON_LOG_LEVEL` | `INFO` | Standard Python log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

```env
# Production — JSON for Datadog / ELK / CloudWatch ingestion
AXON_LOG_FORMAT=json
AXON_LOG_LEVEL=INFO
```

### 3. Token Compression

| Variable | Default | Description |
|---|---|---|
| `AXON_TOKENIZER_MODEL` | `cl100k_base` | tiktoken model used for token counting. `cl100k_base` covers GPT-4, GPT-3.5, and most LiteLLM providers. For Gemini, the `google-genai` SDK client is used when available. |
| `AXON_ENABLED_FORMATS` | *(all 8)* | Comma-separated list of strategies to benchmark per-request. Strategies: `graph`, `graph_session`, `graph_delta`, `generic`, `generic_delta`, `generic_session`, `schema_values`, `json`. |
| `AXON_MAX_SESSIONS` | `1000` | Maximum number of concurrent in-memory sessions tracked for stateful compression. Oldest sessions are evicted when this limit is reached. |

### 4. Memory & Persistence

Axon stores conversation history and session state in a pluggable backend. The default is a local libSQL/SQLite file — zero setup required.

| Variable | Default | Description |
|---|---|---|
| `AXON_MEMORY_TYPE` | `turso` | Backend driver. Options: `turso` (handles both local SQLite files and remote Turso edge), `sqlite`, `redis`. |
| `AXON_TURSO_URL` | `file:./axon_sessions.db` | libSQL connection URL. Use `file:./path/to/db` for local SQLite, `libsql://your-db.turso.io` for remote Turso. |
| `AXON_TURSO_AUTH_TOKEN` | *(none)* | Auth token for remote Turso cloud. Leave unset for local file usage. |
| `AXON_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL. Only used when `AXON_MEMORY_TYPE=redis`. |
| `AXON_MEMORY_DB_PATH` | `./axon_sessions.db` | **@deprecated** — use `AXON_TURSO_URL` instead. Kept for backwards compatibility. |

> [!WARNING]
> In serverless environments (AWS Fargate, Google Cloud Run) or multi-instance deployments, local file storage **will not work** — sessions are lost on restart. Use `redis` or remote Turso instead.

### 5. Security & Access Control

| Variable | Default | Description |
|---|---|---|
| `AXON_ADMIN_API_KEY` | *(none)* | Bearer token required for all `/admin/*` endpoints and the Dashboard. **Must be set in `production` mode.** |
| `AXON_REQUIRE_API_KEY` | `false` | If `true`, all proxy requests must supply `X-API-Key` matching `AXON_API_KEY`. |
| `AXON_API_KEY` | *(none)* | The key to enforce when `AXON_REQUIRE_API_KEY=true`. |
| `AXON_CORS_ORIGINS` | *(none)* | Comma-separated allowed CORS origins. Leave empty to disable CORS (recommended for server-to-server use). **Never set to `*` on a public endpoint.** |
| `AXON_ALLOWED_DOMAINS` | `localhost,127.0.0.1,...` | Comma-separated list of domains allowed for outbound proxy requests. |
| `AXON_ALLOW_ALL_DOMAINS` | `false` | If `true`, bypasses domain allowlist. **Use with caution.** |

### 6. Rate Limiting

Axon includes a built-in, zero-dependency **ASGI rate limiter** using `cachetools.TTLCache`. It replaced the previous `slowapi` integration.

- **Default:** 200 requests per IP per 60-second window
- **Exempt paths:** `/health`, `/metrics` (always bypass the limiter)
- **Response on limit:** `429 Too Many Requests` with `Retry-After: 60` header
- **Configuration:** Set via `app.py` middleware — not via `.env` in the current release

### 7. Gemini Prompt Caching

> [!CAUTION]
> Prompt caching hints are **only safe** when used with provider-native caching (e.g. Gemini `cachedContent`). Do not enable against stateless APIs.

| Variable | Default | Description |
|---|---|---|
| `AXON_ENABLE_GEMINI_PROMPT_CACHE` | `false` | Inject `cache_control` hints for Gemini Context Caching. Requires a **paid** Gemini API plan. |

---

## 🚦 Feature Flags

> [!NOTE]
> Compression and caching features are **ON by default** — they work out of the box on every request. Security, routing, and memory features are **OFF by default** and must be explicitly opted into via your `.env`.

### Always-On (no flag needed)

| Variable | Default | What it does |
|---|---|---|
| `AXON_ENABLE_EXACT_MATCH_CACHE` | `true` | SHA-256 KV cache. 100% savings on repeated identical requests. |
| `AXON_ENABLE_SEMANTIC_CACHE` | `true` | Local vector cache. Catches paraphrased versions of previous questions. |
| `AXON_ENABLE_TOOL_COMPRESSION` | `true` | Compresses JSON Schema tool definitions to compact Python-style signatures. |
| `AXON_ENABLE_VISION_OPTIMIZER` | `true` | Silently downscales base64 images to 768px max before sending to vision APIs. |
| `AXON_ENABLE_AGENTIC_OPTIMIZATIONS` | `true` | Master switch for all 8 agentic compression passes. |
| `AXON_ENABLE_AGENTIC_SCHEMA_DIFF` | `true` | Omits tool JSON schemas for tools the agent hasn't used recently. |
| `AXON_ENABLE_AGENTIC_SCRATCHPAD` | `true` | Deduplicates and compresses `<thinking>` / ReAct scratchpad blocks. |
| `AXON_ENABLE_AGENTIC_OBSERVATION_WINDOW` | `true` | Shannon entropy × recency pruning on old tool results. |
| `AXON_ENABLE_AGENTIC_LOOP_DETECTION` | `true` | Detects duplicate tool calls with identical args. Returns cached result, bypasses LLM. |

### Opt-In (disabled by default)

| Variable | What it unlocks | Extra required? |
|---|---|---|
| `AXON_ENABLE_SEMANTIC_ROUTING=true` | ML Smart Router — routes casual queries to cheaper lite models | `pip install axon-bridge[semantic]` |
| `AXON_ENABLE_PII_REDACTION=true` | Auto-redacts emails, SSNs, credit cards, phones before LLM | `pip install axon-bridge[pii]` for presidio NER |
| `AXON_ENABLE_PROMPT_FIREWALL=true` | Blocks 27 jailbreak and prompt injection patterns | None |
| `AXON_ENABLE_HALLUCINATION_GUARD=true` | Shannon entropy guard on `logprobs` — blocks low-confidence responses | None |
| `AXON_ENABLE_FACT_EXTRACTION=true` | Extracts and stores semantic facts from conversations to persistent memory | None |
| `AXON_ENABLE_LLMLINGUA_COMPRESSION=true` | Semantic NLP compression via LLMLingua-2 local model | `pip install axon-bridge[lingua]` |
| `AXON_ENABLE_AGENT_ROUTES=true` | Agent orchestration endpoints (`/agent/dispatch`, `/agent/swarm`, `/agent/parallel`, `/agent/list`) | None |
| `AXON_ENABLE_ASSISTANTS_ROUTES=true` | OpenAI Assistants API (`beta.threads.*`) + `/v1/swarm/completions` multi-model swarm proxy | None |
| `AXON_ENABLE_TENANT_QUOTAS=true` | Per-tenant USD spend tracking and enforcement | `pip install axon-bridge[redis]` recommended |

---

## 📦 Optional Install Extras

The base `pip install axon-bridge` installs the core proxy + compression. Additional capabilities are unlocked via extras:

```bash
pip install axon-bridge                  # Core proxy — always works
pip install axon-bridge[gemini]          # Google Gemini SDK (google-genai ≥ 1.0)
pip install axon-bridge[semantic]        # ML Smart Router (fastembed + bm25s + numpy)
pip install axon-bridge[pii]             # Advanced PII redaction (presidio-analyzer + spacy)
pip install axon-bridge[web]             # Web/DOM scraping support (trafilatura)
pip install axon-bridge[redis]           # Redis memory backend
pip install axon-bridge[langchain]       # LangChain integration (langchain-core)
pip install axon-bridge[llamaindex]      # LlamaIndex integration (llama-index-core)
pip install axon-bridge[lingua]          # LLMLingua-2 NLP compression (llmlingua)
pip install axon-bridge[telemetry]       # OTLP trace exporter (opentelemetry-exporter-otlp)

# Install multiple extras at once:
pip install axon-bridge[gemini,semantic,pii]
```

| Extra | Key Package | Unlocks |
|---|---|---|
| `gemini` | `google-genai ≥ 1.0` | Native Gemini token counting via the official SDK |
| `semantic` | `fastembed`, `bm25s`, `numpy` | ML Smart Router, semantic vector cache, BM25 pruning |
| `pii` | `presidio-analyzer`, `spacy` | Named Entity Recognition-powered PII redaction |
| `web` | `trafilatura` | DOM pruning and web content extraction |
| `redis` | `redis ≥ 5.0` | Redis memory backend for multi-instance deployments |
| `langchain` | `langchain-core ≥ 0.2` | LangChain runnable integration |
| `llamaindex` | `llama-index-core ≥ 0.10` | LlamaIndex node postprocessor |
| `lingua` | `llmlingua ≥ 0.2.2` | LLMLingua-2 semantic NLP compression |
| `telemetry` | `opentelemetry-exporter-otlp` | OTLP trace export to Jaeger/Grafana Tempo |

---

## 🔌 API Endpoints

### OpenAI-Compatible (`/v1/...`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat/completions` | Chat completions — streaming and non-streaming ✅ verified |
| `GET` | `/v1/models` | List available models |
| `POST` | `/v1/embeddings` | Embeddings proxy |
| `POST` | `/v1/swarm/completions` | Multi-model fan-out swarm — synthesizes all responses *(requires `AXON_ENABLE_ASSISTANTS_ROUTES=true`)* |
| `POST` | `/v1/files` | Upload files for RAG *(requires `AXON_ENABLE_ASSISTANTS_ROUTES=true`)* |
| `GET` | `/v1/files/{id}` | Retrieve file metadata |
| `POST` | `/v1/threads` | Create a stateful thread |
| `POST` | `/v1/threads/{id}/messages` | Add message to thread |
| `POST` | `/v1/threads/{id}/runs` | Execute a thread run |
| `GET` | `/v1/threads/{id}/messages` | List thread messages |
| `POST` | `/batch` | Compress up to 50 payloads in a single HTTP call |

### Agent Orchestration (`/agent/...`)

> Requires `AXON_ENABLE_AGENT_ROUTES=true`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/agent/dispatch` | Route payload to the best matching registered agent |
| `POST` | `/agent/swarm` | Fan out to all registered agents concurrently |
| `POST` | `/agent/parallel` | Dispatch to multiple agent capabilities concurrently |
| `GET` | `/agent/list` | List all registered agents and their capabilities |

### Admin (`/admin/...`)

> All `/admin/*` endpoints require `Authorization: Bearer <AXON_ADMIN_API_KEY>` when the key is set.

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/features` | Get current feature flag states |
| `POST` | `/admin/features` | Toggle feature flags at runtime (no restart needed) |
| `GET` | `/admin/requests` | Live request firehose — last 100 requests |
| `GET` | `/admin/cache` | Semantic cache contents |
| `GET` | `/admin/quotas/{tenant_id}` | Get tenant quota & current spend |
| `POST` | `/admin/quotas/{tenant_id}` | Set tenant quota |

### Ops

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check — returns `{"status": "ok", "version": "0.3.0"}` |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/dashboard` | Observability dashboard |
| `GET` | `/docs` | Interactive OpenAPI docs (Swagger UI) |
| `GET` | `/redoc` | ReDoc API docs |
| `GET` | `/openapi.json` | Raw OpenAPI schema |

---

## 📨 Custom Request Headers

| Header | Example | Description |
|---|---|---|
| `X-Upstream-Base-Url` | `https://api.groq.com/openai/v1` | Override the upstream API base URL per-request (BYOK routing) |
| `X-Axon-Session-ID` | `user-123-session-abc` | Enable session memory, fact extraction, and agentic pipeline |
| `X-Axon-Stateful-Thread: true` | `true` | Send only the new message; Axon rehydrates history from storage |
| `X-Axon-Tenant-ID` | `acme-corp` | Identify tenant for per-tenant USD quota tracking |
| `X-Axon-Max-Spend` | `0.05` | Per-request USD budget cap — Axon kills stream if exceeded |

## 📬 Response Headers

| Header | Example Value | Description |
|---|---|---|
| `x-axon-metrics` | `{"original_tokens": 5507, "compressed_tokens": 3318, "savings_pct": 39.75}` | Token counts and savings for this request |
| `x-axon-cost-saved-usd` | `0.00156` | Estimated dollar savings from compression |
| `x-axon-cache` | `HIT` | Present only when the response was served from L1 (exact) or L2 (semantic) cache |

---

## 🖥️ Running the Server

Axon uses **Granian** (Rust-based ASGI server) for high-throughput, low-latency serving.

```bash
# Standard startup
python -m granian --interface asgi app:app --host 127.0.0.1 --port 8080

# Or via the CLI entry point (if installed via pip)
axon

# Custom port / bind address
python -m granian --interface asgi app:app --host 0.0.0.0 --port 9000
```

---

## 🐳 Docker

The Dockerfile uses a **two-stage `uv` build** — Stage 1 compiles a virtualenv, Stage 2 copies only the venv and source into a lean `python:3.12-slim` runtime image.

```bash
# Build (uses .dockerignore — excludes .git, .venv, tests, __pycache__)
docker build -t axon-bridge .

# Run with your env file
docker run -p 8080:8080 --env-file .env axon-bridge

# Install optional extras during build (edit the Dockerfile RUN line):
# RUN uv pip install --no-cache .[gemini,semantic,pii]
```

| Attribute | Value |
|---|---|
| Base image | `python:3.12-slim` |
| Runtime user | `axon` (non-root) |
| Exposed port | `8080` |
| Healthcheck | `urllib.request.urlopen('http://localhost:8080/health')` |
| Server command | `granian --interface asgi app:app --host 0.0.0.0 --port 8080` |
