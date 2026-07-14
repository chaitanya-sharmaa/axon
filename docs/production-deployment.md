# Production Deployment Guide

This guide covers everything you need to safely run Axon Bridge in production: secrets management, Docker hardening, storage backends, and monitoring.

---

## ✅ Production Readiness Checklist

Before going live, verify each item:

- [ ] **`AXON_ENV=production`** is set — enforces admin key requirement at startup
- [ ] **`AXON_ADMIN_API_KEY`** is set to a strong, randomly generated key — secures `/admin/*` and the Dashboard
- [ ] **`AXON_OPENAI_API_KEY`** is injected from a secrets manager (not hardcoded in `.env`)
- [ ] **`AXON_LOG_FORMAT=json`** is set — enables structured logging for log aggregation
- [ ] **`AXON_CORS_ORIGINS`** is set to your specific frontend domain(s), not `*`
- [ ] **`AXON_MEMORY_TYPE`** is set to `redis` or remote `turso` for multi-instance deployments
- [ ] Docker image is running as **non-root user `axon`** (default in the provided Dockerfile)
- [ ] **Health check** is wired to your load balancer (`GET /health` → `{"status": "ok"}`)
- [ ] **Prometheus scraping** is configured for `GET /metrics`
- [ ] **Rate limiting** defaults (200 req/60s per IP) are reviewed and acceptable for your traffic

---

## 🔐 Secrets Management

### Critical Variables

| Variable | Description | Required in Production? |
|---|---|---|
| `AXON_OPENAI_API_KEY` | Upstream LLM key forwarded to providers | Strongly recommended |
| `AXON_ADMIN_API_KEY` | Secures `/admin/*` and the Dashboard | **Required** (enforced when `AXON_ENV=production`) |
| `AXON_TURSO_AUTH_TOKEN` | Remote Turso cloud auth token | Only if using remote Turso |
| `AXON_REDIS_URL` | Redis connection string (may contain credentials) | Only if using Redis |

### Secret Rotation

Axon loads all settings at startup. Key rotation requires a rolling restart:

1. Update the secret value in your secrets manager (AWS Secrets Manager, Google Secret Manager, HashiCorp Vault).
2. Trigger a rolling restart of your Axon containers — no downtime for stateless proxy requests.
3. Old pods drain their in-flight requests; new pods start with the new key.

> [!CAUTION]
> Rotating `AXON_OPENAI_API_KEY` mid-stream will cause in-flight streaming requests on the old pod to fail at the upstream provider. Plan rotations during low-traffic periods.

> [!NOTE]
> **Settings are validated at startup** by Pydantic V2 `BaseSettings`. A missing `AXON_ADMIN_API_KEY` when `AXON_ENV=production` causes an immediate `ValueError` — the container fails fast rather than starting in an insecure state.

---

## 🐳 Docker

The Dockerfile uses a **two-stage `uv` build** for fast, cache-efficient, lean images.

**Build stages:**
1. **`builder`** — Copies `pyproject.toml`, installs dependencies into `/opt/venv` via `uv pip install --no-cache .`. The large download step is cached as a separate layer.
2. **`runtime`** — `python:3.12-slim` base. Copies only the compiled venv and source. Runs as the non-root `axon` user.

```bash
# Build
# .dockerignore excludes: .git, .venv, venv, tests, __pycache__, .env
docker build -t axon-bridge .

# Run with an env file
docker run -p 8080:8080 --env-file .env axon-bridge

# Override specific vars at runtime
docker run -p 8080:8080 \
  -e AXON_ENV=production \
  -e AXON_ADMIN_API_KEY=your-secret-key \
  -e AXON_OPENAI_API_KEY=sk-... \
  -e AXON_LOG_FORMAT=json \
  axon-bridge
```

**Install optional extras** (edit the `Dockerfile` `RUN` line before building):
```dockerfile
# Default — core proxy only
RUN uv pip install --no-cache .

# With extras
RUN uv pip install --no-cache .[gemini,semantic,pii]
```

| Image attribute | Value |
|---|---|
| Base image | `python:3.12-slim` |
| Runtime user | `axon` (non-root, UID auto-assigned) |
| Exposed port | `8080` |
| Healthcheck interval | 30s, 5s timeout, 10s start period, 3 retries |
| Default CMD | `granian --interface asgi app:app --host 0.0.0.0 --port 8080` |

---

## 💾 Memory & Storage in Production

By default, Axon uses a local libSQL/SQLite file (`axon_sessions.db`) for session history and caching.

> [!WARNING]
> Local file storage **will not work** in serverless environments (AWS Fargate, Google Cloud Run) or multi-instance load-balanced deployments. Data is lost on restart and sessions are out-of-sync across instances.

### Option A: Remote Turso (Recommended for Global)

Turso is a globally distributed libSQL edge database — zero-latency closest-region reads.

```env
AXON_MEMORY_TYPE=turso
AXON_TURSO_URL=libsql://your-db.turso.io
AXON_TURSO_AUTH_TOKEN=your-turso-auth-token
```

### Option B: Redis

Standard Redis for existing Redis infrastructure.

```env
AXON_MEMORY_TYPE=redis
AXON_REDIS_URL=redis://your-redis-cluster:6379/0
# pip install axon-bridge[redis]  required
```

---

## ☸️ Kubernetes

A minimal Deployment + Service for running Axon in a Kubernetes cluster.

```yaml
# axon-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: axon-bridge
  labels:
    app: axon-bridge
spec:
  replicas: 2
  selector:
    matchLabels:
      app: axon-bridge
  template:
    metadata:
      labels:
        app: axon-bridge
    spec:
      containers:
        - name: axon-bridge
          image: your-registry/axon-bridge:0.3.0
          ports:
            - containerPort: 8080
          env:
            - name: AXON_ENV
              value: "production"
            - name: AXON_LOG_FORMAT
              value: "json"
            - name: AXON_MEMORY_TYPE
              value: "redis"
            - name: AXON_OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: axon-secrets
                  key: openai-api-key
            - name: AXON_ADMIN_API_KEY
              valueFrom:
                secretKeyRef:
                  name: axon-secrets
                  key: admin-api-key
            - name: AXON_REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: axon-secrets
                  key: redis-url
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "1000m"
              memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: axon-bridge
spec:
  selector:
    app: axon-bridge
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8080
  type: ClusterIP
```

```bash
# Create secrets (do NOT commit these to git)
kubectl create secret generic axon-secrets \
  --from-literal=openai-api-key="sk-..." \
  --from-literal=admin-api-key="$(openssl rand -hex 32)" \
  --from-literal=redis-url="redis://your-cluster:6379/0"

kubectl apply -f axon-deployment.yaml
```

---

## 🌐 CORS & Network Security

```env
# Development — allow your local frontend
AXON_CORS_ORIGINS=http://localhost:3000

# Production — restrict to your exact domain(s)
AXON_CORS_ORIGINS=https://your-app.com,https://admin.your-app.com
```

> [!CAUTION]
> Do **not** leave `AXON_CORS_ORIGINS` empty or set to `*` on a public-facing deployment. An open CORS policy allows any website to make requests to your proxy on behalf of your users.

---

## 📦 Log Aggregation

Axon outputs structured JSON logs when `AXON_LOG_FORMAT=json`. Every log line includes a `request_id` correlating all log entries for a single request.

```env
AXON_LOG_FORMAT=json
AXON_LOG_LEVEL=INFO
```

**Example JSON log line:**
```json
{
  "timestamp": "2026-07-14T12:00:00Z",
  "level": "INFO",
  "logger": "api.routes.v1_openai_routes",
  "request_id": "52cd99c0-2a5b-4444-a51d-1c48969571b0",
  "message": "Proxying request to groq/llama-3.1-8b-instant",
  "original_tokens": 5507,
  "compressed_tokens": 3318,
  "savings_pct": 39.75
}
```

**Datadog:**
```yaml
# datadog-agent.yaml — tail Axon JSON logs
logs:
  - type: docker
    source: axon-bridge
    service: axon
    auto_multi_line_detection: true
```

**ELK (Filebeat):**
```yaml
filebeat.inputs:
  - type: container
    paths:
      - /var/lib/docker/containers/*/*.log
    processors:
      - add_docker_metadata: ~
      - decode_json_fields:
          fields: ["message"]
          target: ""
```

**CloudWatch Logs** — Use the AWS CloudWatch Logs agent or built-in ECS/Fargate log driver:
```json
{
  "logDriver": "awslogs",
  "options": {
    "awslogs-group": "/axon/production",
    "awslogs-region": "us-east-1",
    "awslogs-stream-prefix": "axon"
  }
}
```
