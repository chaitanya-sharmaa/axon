# Observability & Monitoring

Axon Bridge is designed to be highly observable in production. Every request is traced with a unique `request_id`, every response includes cost metrics in headers, and the full stack is wired to Prometheus + OpenTelemetry.

---

## 🏥 Health Checks

```bash
curl http://localhost:8080/health
# {"status": "ok", "version": "0.3.0"}
```

The `version` field reflects `AXON_APP_VERSION` (default `0.3.0`). Use this endpoint for:
- **Docker** — built-in `HEALTHCHECK` in the Dockerfile (30s interval, 5s timeout, 3 retries)
- **Kubernetes** — `livenessProbe` and `readinessProbe`
- **Load balancers** — AWS ALB / GCP Load Balancer / Nginx upstream check

---

## 📊 Metrics (Prometheus)

Prometheus metrics are exposed at `/metrics` in the standard text format.

```bash
curl http://localhost:8080/metrics
```

### Prometheus Scrape Config

```yaml
# prometheus.yml
scrape_configs:
  - job_name: axon-bridge
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: /metrics
    scrape_interval: 15s
```

### Alerting Rules

```yaml
groups:
  - name: axon_alerts
    rules:
      # 5xx error rate > 5% over 5 minutes
      - alert: AxonHighErrorRate
        expr: rate(fastapi_requests_total{status=~"5.."}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Axon Bridge returning 5xx errors (>5% over 5m)"
          runbook: "Check /admin/requests for recent failed requests"

      # p95 latency > 2.5s
      - alert: AxonHighLatency
        expr: histogram_quantile(0.95, rate(fastapi_requests_duration_seconds_bucket[5m])) > 2.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Axon Bridge p95 latency > 2.5 seconds"

      # Cache miss rate > 80% (cache is not helping)
      - alert: AxonHighCacheMissRate
        expr: |
          rate(fastapi_requests_total{path="/v1/chat/completions"}[10m])
          - rate(fastapi_requests_total{path="/v1/chat/completions", status="200"}[10m])
          > 0.8
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "Axon semantic cache hit rate is low — consider tuning similarity threshold"

      # Rate limit rejections spiking
      - alert: AxonRateLimitSpike
        expr: rate(fastapi_requests_total{status="429"}[5m]) > 10
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Axon is rate-limiting > 10 req/s — a client may be hitting limits"
```

---

## 📝 Structured Logging

For production, output logs in JSON format so they can be ingested by Datadog, ELK, or CloudWatch:

```env
AXON_LOG_FORMAT=json
AXON_LOG_LEVEL=INFO
```

### JSON Log Fields Reference

Every JSON log line from Axon contains these fields:

| Field | Type | Always Present? | Description |
|---|---|---|---|
| `timestamp` | ISO 8601 string | ✅ | UTC timestamp |
| `level` | string | ✅ | `INFO`, `WARNING`, `ERROR`, `DEBUG` |
| `logger` | string | ✅ | Python logger name (e.g. `api.routes.v1_openai_routes`) |
| `request_id` | UUID string | ✅ for requests | Unique ID correlating all logs for a single HTTP request |
| `message` | string | ✅ | Human-readable log message |
| `original_tokens` | int | On compression | Token count before compression |
| `compressed_tokens` | int | On compression | Token count after compression |
| `savings_pct` | float | On compression | Percentage of tokens saved |
| `model` | string | On LLM requests | Target model (e.g. `groq/llama-3.1-8b-instant`) |
| `tenant_id` | string | When set | Value from `X-Axon-Tenant-ID` header |
| `session_id` | string | When set | Value from `X-Axon-Session-ID` header |

**Example:**
```json
{
  "timestamp": "2026-07-14T12:00:00Z",
  "level": "INFO",
  "logger": "api.routes.v1_openai_routes",
  "request_id": "52cd99c0-2a5b-4444-a51d-1c48969571b0",
  "message": "Proxying request to groq/llama-3.1-8b-instant",
  "original_tokens": 5507,
  "compressed_tokens": 3318,
  "savings_pct": 39.75,
  "model": "groq/llama-3.1-8b-instant"
}
```

---

## 📬 Response Headers Reference

Every proxied response includes these headers for real-time, per-request observability:

| Header | Example Value | Description |
|---|---|---|
| `x-axon-metrics` | `{"original_tokens": 5507, "compressed_tokens": 3318, "savings_pct": 39.75}` | JSON blob with full token counts and savings percentage |
| `x-axon-cost-saved-usd` | `0.00156` | Estimated USD saved by compression on this request |
| `x-axon-cache` | `HIT` | Present only when served from L1 (exact match) or L2 (semantic) cache |

> All three headers were confirmed in live end-to-end testing against Groq `llama-3.1-8b-instant` (5,507-token dependency graph payload).

---

## 🔭 OpenTelemetry Traces (OTLP)

Axon is instrumented with `opentelemetry-instrumentation-fastapi` and supports exporting traces to any OTLP-compatible backend (Jaeger, Grafana Tempo, Honeycomb, Datadog).

**Prerequisites:** `pip install axon-bridge[telemetry]`

```env
# .env — enable OTLP trace export
AXON_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

Axon will log a confirmation at startup:
```
INFO  OTLP Trace Exporter configured for http://localhost:4318/v1/traces
```

**Grafana Tempo (via Docker Compose):**
```yaml
# docker-compose.yml
services:
  tempo:
    image: grafana/tempo:latest
    ports:
      - "4318:4318"   # OTLP HTTP
      - "3200:3200"   # Tempo UI

  axon:
    build: .
    environment:
      AXON_OTLP_ENDPOINT: http://tempo:4318/v1/traces
    ports:
      - "8080:8080"
```

**Jaeger (all-in-one):**
```bash
docker run -d --name jaeger \
  -p 4318:4318 \
  -p 16686:16686 \
  jaegertracing/all-in-one:latest

# Then set in .env:
# AXON_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

---

## 🛠️ Tech Stack Summary

| Component | Technology | Notes |
|---|---|---|
| **Web framework** | FastAPI + Starlette | ASGI, full async |
| **Server** | Granian (Rust) | High-throughput ASGI — replaces uvicorn |
| **Settings** | Pydantic V2 `BaseSettings` | `pydantic-settings`; strict type validation at startup |
| **Rate Limiter** | `cachetools.TTLCache` ASGI middleware | 200 req/60s per IP; no external dependency |
| **Schema Validation** | Pydantic V2 `TypeAdapter` + `create_model` | No `jsonschema` dependency |
| **Tracing** | OpenTelemetry SDK + OTLP exporter | `AXON_OTLP_ENDPOINT` to enable |
| **Metrics** | Prometheus via `opentelemetry-exporter-prometheus` | `/metrics` endpoint |
| **Storage** | libSQL (Turso) / SQLite / Redis | Configurable via `AXON_MEMORY_TYPE` |
| **LLM Routing** | LiteLLM | 100+ provider support |
