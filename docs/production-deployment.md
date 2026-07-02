# Production Deployment Guide

Deploying Axon Bridge to production requires attention to security, secrets management, and performance.

## 🚨 Critical Production Secrets

The following environment variables **must** be set securely in production:

1. **`AXON_OPENAI_API_KEY`**: Your upstream LLM provider keys (if you want the server to dictate the key instead of clients bringing their own).
2. **`AXON_ADMIN_API_KEY`**: Secures the `/admin/*` endpoints and the Dashboard. If this is not set, anyone can view your metrics, toggle feature flags, and see your semantic cache!
3. **`AXON_ENV`**: Set this to `production`. Axon will enforce that `AXON_ADMIN_API_KEY` is not empty.

### Secret Rotation Strategy

Axon does not require downtime for most configuration changes, but secret rotation requires a restart since the keys are loaded at application startup into the `settings` singleton.

**Best Practice:**
1. Use a Secrets Manager (AWS Secrets Manager, Google Secret Manager, HashiCorp Vault).
2. Inject secrets as environment variables into your Docker container.
3. When rotating `AXON_OPENAI_API_KEY` or `AXON_ADMIN_API_KEY`, update the secret in your manager and perform a rolling restart of your Axon containers.

---

## 💾 Memory & Storage in Production

By default, Axon uses a local SQLite file (`axon_sessions.db`) for caching and stateful thread memory.

> [!WARNING]  
> If you deploy to a serverless environment (e.g. AWS Fargate, Google Cloud Run) or run multiple load-balanced Axon instances, **local SQLite will not work** (data is lost on restart or out-of-sync across instances).

**Production Solution:**
Change `AXON_MEMORY_TYPE` to `redis` or `turso`.
```env
AXON_MEMORY_TYPE="redis"
AXON_REDIS_URL="redis://your-production-redis-cluster:6379/0"
```

## 🌐 CORS & Security

- Do **not** leave `AXON_CORS_ORIGINS` empty or set to `*` if your proxy is exposed to the public internet.
- Set it explicitly to your frontend application's URL:
  ```env
  AXON_CORS_ORIGINS="https://my-production-app.com"
  ```
