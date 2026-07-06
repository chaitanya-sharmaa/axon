# Observability & Monitoring

Axon Bridge is designed to be highly observable in production environments.

## Health Checks

Axon provides a standard `/health` endpoint for load balancers and Kubernetes probes.

```bash
curl -X GET http://localhost:8080/health
# Response: {"status": "ok", "version": "0.3.0"}
```

## Metrics (Prometheus)

Prometheus metrics are exposed at `/metrics`.

```bash
curl -X GET http://localhost:8080/metrics
```

### Example Grafana/Prometheus Alerting Rules

You can add these rules to your `prometheus.yml` to trigger alerts on high error rates or latency:

```yaml
groups:
  - name: axon_alerts
    rules:
      - alert: AxonHighErrorRate
        expr: rate(fastapi_requests_total{status=~"5.."}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Axon Bridge is returning 5xx errors (>5% over 5m)"

      - alert: AxonHighLatency
        expr: histogram_quantile(0.95, rate(fastapi_requests_duration_seconds_bucket[5m])) > 2.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Axon Bridge p95 latency is > 2.5 seconds"
```

## Structured Logging

For production, it is highly recommended to output logs in JSON format so they can be ingested by Datadog, ELK, or CloudWatch.

Set in your environment:
```env
AXON_LOG_FORMAT="json"
AXON_LOG_LEVEL="INFO"
```

Example output (based on live-verified agent run):
```json
{"timestamp": "2026-07-06T12:00:00Z", "level": "INFO", "message": "Proxying request to groq/llama-3.1-8b-instant", "original_tokens": 5507, "compressed_tokens": 3318, "savings_pct": 39.75}
```

## Response Headers Reference

Every proxied response includes the following headers for real-time observability:

| Header | Example Value | Description |
|---|---|---|
| `x-axon-metrics` | `{"original_tokens": 5507, "compressed_tokens": 3318, "savings_pct": 39.75, "agentic_tokens_saved": 0}` | JSON blob with token counts and savings percentage |
| `x-axon-cost-saved-usd` | `0.00156` | Estimated USD saved by compression on this request |
| `x-axon-cache` | `HIT` | Present only when the response was served from L1 or L2 cache |

All three headers were confirmed in live end-to-end testing against Groq `llama-3.1-8b-instant`.
