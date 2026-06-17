# Axon Configuration Guide

Axon's behavior is highly configurable through environment variables, allowing you to tailor its operation to your specific deployment and security needs. All environment variables are managed by `core/settings.py` and can be set directly in your environment or in a `.env` file.

## General Application Settings

*   **`AXON_APP_TITLE`** (default: `Axon Token Bridge`)
    *   The title displayed in the FastAPI documentation (Swagger UI).
*   **`AXON_APP_VERSION`** (default: `0.3.0`)
    *   The version string for the Axon application.
*   **`AXON_APP_DESCRIPTION`**
    *   A longer description for the FastAPI documentation.
*   **`AXON_OPENAPI_DESCRIPTION`**
    *   Custom description for the OpenAPI specification.
*   **`AXON_OPENAPI_LOGO_URL`**
    *   URL to a logo image to display in the OpenAPI documentation.

## Server Host and Port

*   **`AXON_HOST`** (default: `127.0.0.1`)
    *   The host address on which the FastAPI server will listen. Use `0.0.0.0` to listen on all available network interfaces.
*   **`AXON_PORT`** (default: `8080`)
    *   The port number on which the FastAPI server will listen.

## Core Functionality Settings

*   **`AXON_INCLUDE_JSON_FALLBACK`** (default: `true`)
    *   If `true`, the Axon envelope will include the original (normalized) JSON payload alongside the `compact_text`. This is useful for debugging or for clients that might not yet support GCF decoding.
*   **`AXON_MEMORY_DB_PATH`** (default: `/tmp/axon_sessions.db`)
    *   The file path for the SQLite database used by the `SqliteMemoryStore` to persist session data and event logs.
*   **`AXON_MEMORY_TYPE`** (default: `sqlite`)
    *   Backend for session state. Use `sqlite` for standalone/lightweight setups or `redis` for distributed clusters.
*   **`AXON_REDIS_URL`** (default: `redis://localhost:6379/0`)
    *   Connection URL for the Redis backend when `AXON_MEMORY_TYPE` is `redis`.
*   **`AXON_TOKENIZER_MODEL`** (default: `cl100k_base`)
    *   The default `tiktoken` model to use for token estimation if a specific `target_model` is not provided or its tokenizer cannot be loaded.

## Security Settings

These settings are managed by the `SecurityPolicy` service.

*   **`AXON_REQUIRE_API_KEY`** (default: `false`)
    *   If `true`, all requests to the `/proxy/upstream` endpoint (and potentially other secured routes) will require an `X-API-Key` header with a valid API key.
*   **`AXON_API_KEY`**
    *   The secret API key string that clients must provide in the `X-API-Key` header when `AXON_REQUIRE_API_KEY` is `true`.
*   **`AXON_ALLOW_ALL_DOMAINS`** (default: `false`)
    *   **WARNING**: Only use in trusted, isolated development environments. If `true`, the `/proxy/upstream` endpoint will bypass the domain allowlist, allowing requests to any external domain.
*   **`AXON_ALLOWED_DOMAINS`** (comma-separated list)
    *   A comma-separated list of domains that the `/proxy/upstream` endpoint is permitted to forward requests to. Example: `api.github.com,httpbin.org,localhost`.

## Route Prefixing

You can add prefixes to groups of routes, which is useful when deploying Axon behind a reverse proxy or as part of a larger API gateway.

*   **`AXON_ROUTE_PREFIX_CORE`** (default: empty)
    *   Prefix for core routes (`/health`, `/translate`).
*   **`AXON_ROUTE_PREFIX_PROCESS`** (default: empty)
    *   Prefix for process routes (`/process`).
*   **`AXON_ROUTE_PREFIX_PROXY`** (default: `/proxy`)
    *   Prefix for proxy routes (`/proxy/upstream`).
*   **`AXON_ROUTE_PREFIX_MEMORY`** (default: `/memory`)
    *   Prefix for memory routes (`/memory/sessions`, etc.).
*   **`AXON_ROUTE_PREFIX_SECURITY`** (default: `/security`)
    *   Prefix for security configuration routes (`/security/config`, etc.).

## Route Enabling/Disabling

You can selectively enable or disable entire groups of routes, which is useful for minimizing the API surface or for specific deployment scenarios.

*   **`AXON_ENABLE_CORE_ROUTES`** (default: `true`)
*   **`AXON_ENABLE_PROCESS_ROUTES`** (default: `true`)
*   **`AXON_ENABLE_PROXY_ROUTES`** (default: `true`)
*   **`AXON_ENABLE_MEMORY_ROUTES`** (default: `true`)
*   **`AXON_ENABLE_SECURITY_ROUTES`** (default: `true`)

## Example `.env` File

```dotenv
AXON_HOST=0.0.0.0
AXON_PORT=8000
AXON_REQUIRE_API_KEY=true
AXON_API_KEY="my-super-secret-key"
AXON_ALLOWED_DOMAINS="api.example.com,my-internal-service.local"
AXON_MEMORY_DB_PATH="/var/lib/axon/sessions.db"
AXON_ROUTE_PREFIX_PROXY="/api/v1/axon/proxy"
```