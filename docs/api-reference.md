# API & Configuration Reference

This document covers all configurable environment variables for Axon Bridge, as well as the API endpoints exposed by the proxy.

---

## ⚙️ Configuration Reference

### Core Settings

| Variable | Default | Description |
|---|---|---|
| `AXON_HOST` | `127.0.0.1` | Bind address (`0.0.0.0` to expose on network) |
| `AXON_PORT` | `8080` | Listen port |
| `AXON_OPENAI_API_KEY` | — | Your upstream LLM API key. If empty, clients must Bring Their Own Key (BYOK) |
| `AXON_OPENAI_BASE_URL` | — | Your default upstream Base URL. If empty, clients can pass `X-Upstream-Base-Url` header |
| `AXON_DEFAULT_MODEL` | `gpt-4o` | Default model when none is specified |

### Caching & Compression

| Variable | Default | Description |
|---|---|---|
| `AXON_ENABLED_FORMATS` | `(all 8)` | Comma-separated list of compression strategies to benchmark |
| `AXON_TOKENIZER_MODEL` | `cl100k_base` | Tokenizer for token count estimation |
| `AXON_SEMANTIC_CACHE` | `true` | Enable/disable semantic vector cache |
| `AXON_ENABLE_LLMLINGUA_COMPRESSION` | `false` | Enable/disable semantic NLP compression using LLMLingua-2 |
| `AXON_ENTROPY_THRESHOLD` | `1.5` | Shannon entropy threshold for hallucination guard |

### Stateful Compression (Advanced)

| Variable | Default | Description |
|---|---|---|
| `AXON_ENABLE_STATEFUL_COMPRESSION` | `false` | Enable TOON/TRON destructive deduplication. **Only safe with Anthropic/Gemini provider caching.** |
| `AXON_ENABLE_GEMINI_PROMPT_CACHE` | `false` | Inject `cache_control` hints for Gemini Context Caching (paid plan only) |

### Memory & Persistence

| Variable | Default | Description |
|---|---|---|
| `AXON_MEMORY_TYPE` | `turso` | Memory backend (`turso`, `sqlite`, or `redis`). The `turso` driver handles both local SQLite files and remote Turso edges. |
| `AXON_TURSO_URL` | `file:./axon_sessions.db` | libSQL/Turso connection URL. Use `file:./axon_sessions.db` for local SQLite or `libsql://...` for remote Turso. |
| `AXON_TURSO_AUTH_TOKEN` | — | Auth token for remote Turso cloud database. Leave unset for local file usage. |
| `AXON_MEMORY_DB_PATH` | `./axon_sessions.db` | @deprecated — use `AXON_TURSO_URL` instead. Kept for backwards compatibility. |
| `AXON_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL (when `AXON_MEMORY_TYPE=redis`) |

### Security & Quotas

| Variable | Default | Description |
|---|---|---|
| `AXON_ADMIN_API_KEY` | — | Bearer token required for all `/admin/*` endpoints. Leave unset for open dev access. |
| `AXON_REQUIRE_API_KEY` | `false` | Enforce `X-API-Key` on all proxy requests |
| `AXON_ENABLE_TENANT_QUOTAS` | `false` | Enable per-tenant USD spend tracking and enforcement |
| `AXON_CORS_ORIGINS` | — | Comma-separated allowed CORS origins (e.g. `http://localhost:3000`) |

### Feature Flags (Runtime-Toggleable)

> [!NOTE]
> Compression features are **ON by default**. Security, routing, and memory features are **OFF by default** — opt-in explicitly.

**Always-On Compression Features (no flag needed)**

| Variable | Default | Description |
|---|---|---|
| `AXON_ENABLE_EXACT_MATCH_CACHE` | `true` | SHA-256 exact-match KV cache — 100% savings on repeated requests |
| `AXON_ENABLE_SEMANTIC_CACHE` | `true` | L2 local vector cache for semantically similar queries |
| `AXON_ENABLE_TOOL_COMPRESSION` | `true` | Compress JSON Schema tool definitions to Python signatures |
| `AXON_ENABLE_VISION_OPTIMIZER` | `true` | Downscale base64 images to 768px to reduce vision tokens |
| `AXON_ENABLE_AGENTIC_OPTIMIZATIONS` | `true` | Master switch for the 8-pass agentic pipeline |
| `AXON_ENABLE_AGENTIC_SCHEMA_DIFF` | `true` | Tool schema differential transmission |
| `AXON_ENABLE_AGENTIC_SCRATCHPAD` | `true` | ReAct scratchpad compression |
| `AXON_ENABLE_AGENTIC_OBSERVATION_WINDOW` | `true` | Entropy-based observation pruning |
| `AXON_ENABLE_AGENTIC_LOOP_DETECTION` | `true` | Tool-call loop circuit breaker |

**Opt-In Features (disabled by default)**

| Variable | Default | Description |
|---|---|---|
| `AXON_ENABLE_SEMANTIC_ROUTING` | `false` | ML-powered lite/pro model routing using local sentence-transformers |
| `AXON_ENABLE_RAG_CONTEXT` | `false` | File attachment vector search for RAG context injection |
| `AXON_ENABLE_PROMPT_FIREWALL` | `false` | Block 25+ known jailbreak and prompt-injection patterns |
| `AXON_ENABLE_PII_REDACTION` | `false` | Auto-redact emails, SSNs, credit cards, and phone numbers |
| `AXON_ENABLE_HALLUCINATION_GUARD` | `false` | Shannon entropy guard on logprobs — blocks low-confidence responses |
| `AXON_ENABLE_FACT_EXTRACTION` | `false` | Extract and store semantic facts from conversations |
| `AXON_ENABLE_LLMLINGUA_COMPRESSION` | `false` | Semantic NLP compression via LLMLingua-2 local model |
| `AXON_ENABLE_AGENT_ROUTES` | `false` | Agent registration, dispatch, and swarm routing endpoints |
| `AXON_ENABLE_ASSISTANTS_ROUTES` | `false` | OpenAI Assistants API (beta.threads.*) compatibility routes |
| `AXON_ENABLE_TENANT_QUOTAS` | `false` | Per-tenant USD spend tracking and enforcement |
| `AXON_ENABLE_GEMINI_PROMPT_CACHE` | `false` | Gemini Context Caching via cache_control hints (paid plan only) |

---

## 🔌 API Reference

### OpenAI-Compatible Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat/completions` | Chat completions (streaming + non-streaming) |
| `GET` | `/v1/models` | List available models |
| `POST` | `/v1/embeddings` | Embeddings proxy |
| `POST` | `/v1/files` | Upload files for RAG |
| `GET` | `/v1/files/{id}` | Retrieve file metadata |
| `POST` | `/v1/threads` | Create a stateful thread |
| `POST` | `/v1/threads/{id}/messages` | Add message to thread |
| `POST` | `/v1/threads/{id}/runs` | Execute a thread run |
| `GET` | `/v1/threads/{id}/messages` | List thread messages |

### Custom Axon Headers

| Header | Description |
|---|---|
| `X-Upstream-Base-Url` | (BYOK) Dynamic upstream API base URL for agents connecting to custom providers or models |
| `X-Axon-Session-ID` | Session ID for memory/fact extraction |
| `X-Axon-Stateful-Thread: true` | Enable stateful thread rehydration |
| `X-Axon-Tenant-ID` | Tenant identifier for quota tracking |
| `X-Axon-Max-Spend: 0.05` | Per-request USD budget (stream circuit breaker) |

### Response Headers

| Header | Description |
|---|---|
| `x-axon-metrics` | JSON blob: `{original_tokens, compressed_tokens, savings_pct}` |
| `x-axon-cost-saved-usd` | Estimated dollar savings for this request |
| `x-axon-cache` | `HIT` if response served from cache |

### Admin Endpoints

> **Note:** All `/admin/*` endpoints require `Authorization: Bearer <AXON_ADMIN_API_KEY>` if the key is set.

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/features` | Get current feature flag states |
| `POST` | `/admin/features` | Toggle feature flags at runtime |
| `GET` | `/admin/requests` | Live request firehose (last 100) |
| `GET` | `/admin/cache` | Semantic cache contents |
| `GET` | `/admin/quotas/{tenant_id}` | Get tenant quota & spend |
| `POST` | `/admin/quotas/{tenant_id}` | Set tenant quota |
| `GET` | `/metrics` | Prometheus metrics endpoint |
| `GET` | `/dashboard` | React observability dashboard |
| `GET` | `/docs` | Interactive OpenAPI docs |
