# Changelog

All notable changes to Axon Bridge are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **Asynchronous Swarm Routing** (`/v1/swarm/completions`) — concurrent multi-model fan-out with automatic LLM synthesis and SSE streaming
- **OpenAI-compatible proxy** (`/v1/chat/completions`, `/v1/models`, `/v1/embeddings`) — point any OpenAI SDK client at Axon for automatic token compression with zero code changes
- **Streaming support** — `/v1/chat/completions` passes through SSE streams from upstream
- **Batch endpoint** (`POST /batch`) — compress up to 50 payloads in a single HTTP call
- **Dollar cost reporting** — `metrics` now includes `estimated_cost_saved_usd` when model pricing is known
- **Model pricing database** (`services/pricing.py`) — covers GPT-4o, GPT-4, GPT-3.5, Claude 3 family
- **LangChain callback handler** (`integrations/langchain.py`) — measure and report savings via `AxonCallbackHandler`
- **Plugin system** (`services/plugin_registry.py`) — register custom encoding strategies via `@register_strategy`
- **CLI** (`cli.py`) — `axon serve`, `axon benchmark`, `axon encode`, `axon pricing`, `axon session show/clear`
- **Structured JSON logging** (`core/logging_config.py`) — enable with `AXON_LOG_FORMAT=json`
- **Request-ID middleware** — every request gets an `X-Request-ID` header propagated through all log lines
- **Liveness / readiness health checks** — `/health/live` and `/health/ready` (separate Kubernetes probes)
- **`python-dotenv` support** — `.env` files loaded automatically at startup
- **`pyproject.toml`** — proper PyPI-ready packaging with optional dependency groups
- **Docker support** — multi-stage `Dockerfile` and `docker-compose.yml` (SQLite) + `docker-compose.redis.yml` (Redis)
- **`.env.example`** — template with every `AXON_*` variable documented
- **CORS middleware** — configurable via `AXON_CORS_ORIGINS`
- **Rate limiting** (`cachetools.TTLCache` ASGI middleware) — per-IP limits, 200 req/60s by default; `/health` and `/metrics` are exempt
- **Payload cache** (`services/payload_cache.py`) — LRU cache keyed on SHA-256 eliminates re-encoding identical payloads
- **Graceful shutdown** — SQLite connection closed cleanly on app shutdown
- **LRU eviction for session state** — `TokenOptimizer` now caps in-memory session state (default 1 000 sessions)
- **`max_sessions` setting** (`AXON_MAX_SESSIONS`) — controls the LRU cap
- **Agentic Optimization Pipeline** — 7-pass mathematical compression layer (`services/agentic/pipeline.py`): error truncation, whitespace normalization, scratchpad compression, parallel deduplication, prefix caching, schema differential, observation window pruning
- **Loop Circuit Breaker** — separate from the pipeline; detects and short-circuits identical repeated tool calls with zero LLM spend
- **Prompt Firewall** — expanded to 27 jailbreak/injection detection patterns
- **Shannon Entropy Hallucination Guard** — logprobs entropy analysis to block low-confidence responses
- **Real-time Observability Dashboard** — 10-tab dashboard at `/dashboard` with live metrics, cache explorer, security log, tenant quotas, sessions, API playground, agentic telemetry, and feature flag control

### Fixed
- `bridge_service.py`: fixed runtime crash where non-existent `encode_best_effort()` was called
- `token_optimizer.py`: removed stray unreachable docstring after `return` statement
- `security_policy.py`: replaced timing-unsafe `==` API key comparison with `hmac.compare_digest`
- `proxy_routes.py`: added `follow_redirects=False` to prevent SSRF via redirect chains
- `proxy_routes.py`: removed domain allowlist from 403 error response (info-leak)
- `sqlite_memory_store.py`: switched from per-call connections to a single persistent connection + WAL mode
- `sqlite_memory_store.py`: added `ON DELETE CASCADE` to FK constraints
- All datetime calls: replaced deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)`
- `tokenizer_factory.py`: Anthropic client is now lazily instantiated (only when a Claude model is requested)
- `bridge_service.py`: removed unused `import tiktoken`

---

## [0.3.0] — 2026-04-01

### Added
- Multi-agent orchestration layer (`services/agent_orchestrator.py`)
- Redis memory backend (`services/redis_memory_store.py`)
- Agent routes: `/agent/dispatch`, `/agent/parallel`, `/agent/swarm`, `/agent/list`
- `schema_values` encoding strategy for flat repetitive data
- `generic_delta` (TOON for generics) and `generic_session` (TRON for generics) strategies
- Per-call `enabled_strategies` override in `TokenOptimizer.optimize()`
- Model-aware token counting (OpenAI via tiktoken, Anthropic via client API)

### Changed
- `AxonService` now delegates all session management to `TokenOptimizer` (single source of truth)
- `SecurityConfig.validate_api_key` made configurable at runtime

---

## [0.2.0] — 2026-02-01

### Added
- SQLite-backed persistent session memory (`services/sqlite_memory_store.py`)
- Security policy: domain allowlist + API key validation
- Memory routes: `/memory/sessions`, `/memory/session/{id}`, cleanup
- Security routes: `/security/config`, domain management, API key toggle
- Configurable route prefixes and feature flags via env vars

---

## [0.1.0] — 2026-01-01

### Added
- Initial release
- `TokenOptimizer` with graph + generic Axon strategies
- `AxonService` wrapper with `process()` / `process_async()`
- FastAPI server with `/process`, `/translate/in`, `/translate/out`
- Proxy endpoint `/proxy/upstream`
- SQLite session memory (basic)
