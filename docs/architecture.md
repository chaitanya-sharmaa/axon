# Architecture Reference

This document provides comprehensive system architecture diagrams for Axon Bridge. All diagrams reflect the actual code structure as of version `0.3.0`.

---

## 1. Full Request Pipeline

Every incoming request flows through the following stages before reaching the upstream LLM:

```mermaid
flowchart TD
    Client["Client / OpenAI SDK\nPOST /v1/chat/completions"]:::client

    Client --> RateLimit{"In-Process Rate Limiter\ncachetools.TTLCache\n200 req/60s per IP"}

    RateLimit -->|"429 Too Many Requests"| Reject1["429 Response"]:::error
    RateLimit -->|"OK"| CostGuard{"Cost Budget Guard\nX-Axon-Max-Spend header"}

    CostGuard -->|"Budget exceeded mid-stream"| Kill["Kill TCP Connection"]:::error
    CostGuard -->|"OK"| L1{"L1 Exact-Match KV Cache\nSHA-256 lookup"}

    L1 -->|"HIT — 100% savings"| ResponsePath
    L1 -->|"MISS"| Firewall{"Prompt Firewall\n27 injection patterns"}

    Firewall -->|"BLOCKED — 403"| Reject2["403 SYSTEM HALTED."]:::error
    Firewall -->|"SAFE"| PII["PII Redactor\nSSN / CC / Email / Phone"]

    PII --> L2{"L2 Semantic Vector Cache\nFastEmbed similarity"}
    L2 -->|"HIT — ~100% savings"| ResponsePath
    L2 -->|"MISS"| Router["ML Smart Router\nsentence-transformers"]

    Router -->|"lite model"| Agentic["Agentic Pipeline\n7 ordered passes"]:::agentic
    Router -->|"pro model"| Agentic

    Agentic --> Compress["Token Optimizer\n8 structural strategies"]:::axon
    Compress -->|"Compressed payload"| LLM["OpenAI / Gemini /\nAnthropic / Groq / Ollama\nvia LiteLLM"]:::llm

    LLM -->|"logprobs"| Entropy{"Shannon Entropy Guard"}:::guard
    Entropy -->|"entropy > threshold"| JSONHeal["JSON Healing Retry\nup to 3 attempts"]
    Entropy -->|"OK"| ResponsePath

    JSONHeal --> ResponsePath["Build Response\nx-axon-metrics header\nx-axon-cost-saved-usd header"]:::axon
    ResponsePath --> StoreCache["Store in L1 + L2 Cache"]:::cache
    StoreCache --> Client

    classDef client fill:#1e3a5f,stroke:#2563eb,color:#e0f2fe
    classDef axon fill:#2563eb,stroke:#1d4ed8,color:#fff
    classDef cache fill:#059669,stroke:#047857,color:#fff
    classDef guard fill:#dc2626,stroke:#b91c1c,color:#fff
    classDef error fill:#ef4444,stroke:#b91c1c,color:#fff
    classDef llm fill:#7c3aed,stroke:#6d28d9,color:#fff
    classDef agentic fill:#d97706,stroke:#b45309,color:#fff
```

---

## 2. Agentic Optimization Pipeline

The 7-pass pipeline runs automatically when `X-Axon-Session-ID` is present. Stateless passes always run; session-aware passes activate when a session ID is provided.

```mermaid
flowchart LR
    IN["Incoming\nmessages + tools"]:::input

    IN --> P1["Pass 1\nError Truncation\nStateless ~0ms"]:::stateless
    P1 --> P2["Pass 2\nWhitespace Normalization\nStateless ~0ms"]:::stateless
    P2 --> P3["Pass 3\nScratchpad Compression\nStateless ~1ms"]:::stateless
    P3 --> P4["Pass 4\nParallel Deduplication\nStateless ~1ms"]:::stateless

    P4 --> HasSession{"Session ID\npresent?"}

    HasSession -->|"No"| OUT
    HasSession -->|"Yes"| P5["Pass 5\nPrefix Caching\nSession-aware ~0ms"]:::session
    P5 --> P6["Pass 6\nTool Schema Differential\nSession-aware ~1ms"]:::session
    P6 --> P7["Pass 7\nObservation Window Pruning\nShannon entropy x recency\nSession-aware ~2ms"]:::session
    P7 --> OUT

    OUT["Optimized\nmessages + tools"]:::output

    classDef input fill:#1e3a5f,color:#e0f2fe
    classDef stateless fill:#2563eb,color:#fff
    classDef session fill:#d97706,color:#fff
    classDef output fill:#059669,color:#fff
```

> **Loop Circuit Breaker** is a separate mechanism (`check_loop` / `record_tool_call`) that runs *before* the pipeline and short-circuits identical repeated tool calls with **100% LLM bypass**.

### Pipeline Savings at a Glance

| Pass | Module | Scope | Typical Savings |
|---|---|---|---|
| 1 | `error_truncator` | Stack trace → single line | **~90%** on tool failures |
| 2 | `whitespace_normalizer` | Unicode + whitespace cleanup | **5–15%** |
| 3 | `scratchpad_compressor` | `<thinking>` / ReAct dedup | **30–50%** on reasoning |
| 4 | `parallel_deduplicator` | Cross-tool field dedup | **15–40%** |
| 5 | `prefix_cacher` | Provider KV cache markers | **85–90%** on fixed prefixes |
| 6 | `tool_schema_diff` | Skip unused tool schemas | **80%** on schemas |
| 7 | `observation_window` | Entropy-based history prune | **40–70%** on history |
| ± | Loop Circuit Breaker *(separate)* | Detect identical tool calls | **100%** — bypasses LLM |

---

## 3. Token Compression Strategies

The `TokenOptimizer` benchmarks every payload against all 8 strategies and picks the winner with the lowest token count.

```mermaid
graph TD
    Input["Raw JSON Payload"]:::input --> Bench{"TokenOptimizer\nBenchmarks All 8 Strategies"}:::axon

    Bench --> S1["Error Truncation\nStack trace minimizer"]
    Bench --> S2["Whitespace Normalization\nStrips filler"]
    Bench --> S3["Scratchpad Compression\nPrunes reasoning"]
    Bench --> S4["Parallel Deduplication\nRemoves duplicates"]
    Bench --> S5["Prefix Caching\nAuto cache_control"]
    Bench --> S6["Schema Differential\nPrunes old tools"]
    Bench --> S7["Observation Window\nEntropy pruning"]
    Bench --> S8["Loop Circuit Breaker\n100% LLM Bypass"]

    S1 --> Pick{"Select Lowest\nToken Count"}:::axon
    S2 --> Pick
    S3 --> Pick
    S4 --> Pick
    S5 --> Pick
    S6 --> Pick
    S7 --> Pick
    S8 --> Pick

    Pick --> Out["Compressed Payload to LLM"]:::output

    classDef input fill:#1e3a5f,color:#e0f2fe
    classDef axon fill:#2563eb,color:#fff
    classDef output fill:#059669,color:#fff
```

**Verified benchmark results:**

| Payload | Strategy | Token Savings |
|---|---|---|
| Python Stack Trace (Error Log) | Error Truncation | **99.6%** (4,240→19 tokens) |
| Infinite Tool Calling Loop | Loop Circuit Breaker | **100% LLM Bypass** ($0 cost) |
| Kubernetes YAML | Whitespace/Syntax Normalization | **15.9%** |
| AWS EC2 JSON Response | Structural Compression | **14.3%** |
| Verbose JSON Schema Tools | Tool Schema Optimization | **25.3%** (455→340 tokens) |

---

## 4. Caching Layers (L1 + L2)

```mermaid
sequenceDiagram
    participant Client
    participant L1 as L1 Exact-Match Cache<br/>(SHA-256 KV)
    participant L2 as L2 Semantic Cache<br/>(FastEmbed vectors)
    participant LLM as Upstream LLM

    Client->>L1: POST /v1/chat/completions
    alt Identical request seen before
        L1-->>Client: Cache HIT — x-axon-cache: HIT (100% savings ~5ms)
    else New request
        L1->>L2: MISS — check semantic cache
        alt Paraphrased question above similarity threshold
            L2-->>Client: Cache HIT — x-axon-cache: HIT (~100% savings)
        else Fully new question
            L2->>LLM: Forward compressed payload
            LLM-->>L2: LLM response
            L2->>L1: Store in both caches
            L2-->>Client: Response + x-axon-metrics header
        end
    end
```

---

## 5. Multi-Tenant Cost Tracking

```mermaid
graph LR
    Req["Incoming Request\nX-Axon-Tenant-ID: acme"]:::client --> GW["Axon Proxy"]:::axon
    GW --> Check{"Check Quota\nRedis / Turso"}:::axon
    Check -->|"Budget exceeded"| Rej["429 Too Many Requests"]:::error
    Check -->|"Budget available"| Route["Route to LLM"]:::axon

    Route --> LLM["OpenAI / Anthropic / Gemini"]:::llm
    LLM --> Calc["Calculate tokens used\nConvert to USD"]:::axon
    Calc --> Store[("Redis / Turso\nAtomic increment")]:::db

    classDef client fill:#1e3a5f,stroke:#2563eb,color:#e0f2fe
    classDef axon fill:#2563eb,stroke:#1d4ed8,color:#fff
    classDef error fill:#ef4444,stroke:#b91c1c,color:#fff
    classDef llm fill:#7c3aed,stroke:#6d28d9,color:#fff
    classDef db fill:#d97706,stroke:#b45309,color:#fff
```

---

## 6. Security: Firewall & PII Flow

```mermaid
sequenceDiagram
    participant Client
    participant Firewall as Prompt Firewall<br/>(27 patterns)
    participant PII as PII Redactor<br/>(regex + optional presidio NER)
    participant LLM as Upstream LLM

    Client->>Firewall: POST with user message
    alt Jailbreak or injection detected
        Firewall-->>Client: 403 SYSTEM HALTED.
    else Safe message
        Firewall->>PII: Forward safe message
        alt PII detected SSN / CC / Email / Phone
            PII->>PII: Redact sensitive data
            PII->>LLM: Redacted message
        else No PII
            PII->>LLM: Original message
        end
        LLM-->>Client: Response without PII echo
    end
```

---

## 7. JSON Healing Loop

When `response_format.json_schema` is requested and the LLM returns malformed JSON:

```mermaid
sequenceDiagram
    participant Agent
    participant Axon
    participant LLM

    Agent->>Axon: POST /v1/chat/completions with json_schema
    Axon->>LLM: Forward request
    LLM-->>Axon: bad json with trailing comma
    Note over Axon: JSONDecodeError — Healing triggered attempt 1 of 3
    Axon->>LLM: Append error and retry
    LLM-->>Axon: valid json but missing required field
    Note over Axon: Pydantic V2 TypeAdapter validation fails — attempt 2 of 3
    Axon->>LLM: Append schema error and retry
    LLM-->>Axon: valid json with all required fields
    Axon-->>Agent: Clean validated response
```

---

## 8. Agent Orchestration Routes

```mermaid
graph TD
    Client["Client App"]:::client --> AE{"AXON_ENABLE_AGENT_ROUTES=true"}

    AE --> DR["POST /agent/dispatch\nRoute to best single agent"]:::route
    AE --> SR["POST /agent/swarm\nFan out to all agents"]:::route
    AE --> PR["POST /agent/parallel\nDispatch by capability"]:::route
    AE --> LR["GET /agent/list\nList registered agents"]:::route

    Client --> BE{"AXON_ENABLE_ASSISTANTS_ROUTES=true"}
    BE --> SC["POST /v1/swarm/completions\nMulti-model fan-out + synthesis"]:::route

    DR --> Orch["AgentOrchestrator\nservices/agent_orchestrator.py"]:::axon
    SR --> Orch
    PR --> Orch
    SC --> LiteLLM["LiteLLM\n100+ providers"]:::llm

    classDef client fill:#1e3a5f,color:#e0f2fe
    classDef route fill:#059669,color:#fff
    classDef axon fill:#2563eb,color:#fff
    classDef llm fill:#7c3aed,color:#fff
```

---

## 9. Memory & Persistence Backends

```mermaid
graph LR
    App["Axon Bridge"]:::axon --> Decision{"AXON_MEMORY_TYPE"}

    Decision -->|"turso"| Turso["libSQL / Turso\nfile:./axon_sessions.db\nor libsql://your-db.turso.io"]:::db
    Decision -->|"redis"| Redis["Redis\nredis://localhost:6379/0"]:::db
    Decision -->|"sqlite"| SQLite["SQLite\n./axon_sessions.db"]:::db

    Turso --> Features["Session History\nFact Extraction\nTenant Quotas\nAgentic State"]
    Redis --> Features
    SQLite --> Features

    classDef axon fill:#2563eb,color:#fff
    classDef db fill:#d97706,color:#fff
```

> [!WARNING]
> In serverless environments (AWS Fargate, Google Cloud Run) or multi-instance deployments, local file storage (`turso` with `file:./` or `sqlite`) **will not work** — sessions are lost on restart. Use `redis` or remote Turso (`libsql://`) instead.

---

## 10. Tech Stack Summary

| Component | Technology | Notes |
|---|---|---|
| **Web framework** | FastAPI + Starlette | ASGI, full async |
| **ASGI server** | Granian (Rust) | High-throughput — replaces uvicorn |
| **LLM routing** | LiteLLM | 100+ provider support |
| **Settings** | Pydantic V2 `BaseSettings` | `pydantic-settings`; strict type validation at startup |
| **Rate limiter** | `cachetools.TTLCache` ASGI middleware | 200 req/60s per IP; no external dependency |
| **Schema validation** | Pydantic V2 `TypeAdapter` + `create_model` | No `jsonschema` dependency |
| **Token counting** | `tiktoken` (OpenAI) / `google-genai` (Gemini) | Provider-aware factory |
| **Compression** | `gcf-python` (GCF graph/generic formats) | 8 strategies benchmarked per request |
| **Vector cache** | `fastembed` | Local embedding model; no external API |
| **Tracing** | OpenTelemetry SDK + OTLP exporter | `AXON_OTLP_ENDPOINT` to enable |
| **Metrics** | Prometheus via `opentelemetry-exporter-prometheus` | `/metrics` endpoint |
| **Storage** | libSQL (Turso) / SQLite / Redis | Configurable via `AXON_MEMORY_TYPE` |
| **Image handling** | Pillow | Vision downscaling to 768px max |
| **JSON serialization** | `orjson` | Fast binary JSON; used throughout |
