# Axon API Endpoint Reference

This document provides a detailed reference for all API endpoints exposed by the Axon Bridge.

## Base URL

`http://127.0.0.1:8080` (or as configured by `AXON_HOST` and `AXON_PORT`)

## Common Request Headers

*   `Content-Type: application/json` (for most POST requests)
*   `X-API-Key: <your-secret-key>` (if API key authentication is enabled)

## Common Response Fields (Axon Envelope)

Many endpoints return an Axon envelope, which typically includes:

*   **`compact_text`** (`string`): The token-optimized payload, ready to be sent to an LLM.
*   **`profile`** (`string`): The GCF profile used for `compact_text` (e.g., `graph`, `generic`, `delta`).
*   **`metrics`** (`object`): Token savings statistics.
    *   `estimated_json_tokens` (`integer`): Estimated tokens if raw JSON were sent.
    *   `estimated_compact_tokens` (`integer`): Estimated tokens for the `compact_text`.
    *   `estimated_savings_percent` (`float`): Percentage of tokens saved.
    *   `strategy_used` (`string`): The winning optimization strategy (e.g., `graph_session`, `generic_delta`).
    *   `payload_type` (`string`): Detected type of the payload (`graph` or `generic`).
    *   `format_comparison` (`object`): Detailed token estimates for all evaluated strategies.
*   **`session_id`** (`string`, optional): The session ID if provided in the request.
*   **`json`** (`object`, optional): The original (normalized) JSON payload, included if `AXON_INCLUDE_JSON_FALLBACK` is `true`.

---

## 1. Core Endpoints (`/` or `AXON_ROUTE_PREFIX_CORE`)

### `GET /health`

*   **Description**: Checks the health status of the Axon Bridge.
*   **Response**: `{"status": "ok"}`
*   **Status Codes**: `200 OK`

### `POST /translate/in`

*   **Description**: Converts any input format (JSON string, GCF string, Python object) into a normalized Python object. Useful for debugging input parsing.
*   **Request Body**: Any valid JSON or GCF string.
*   **Response**: `{"object": <normalized_python_object>}`
*   **Status Codes**: `200 OK`, `422 Unprocessable Entity` (for invalid input)

### `POST /translate/out`

*   **Description**: Encodes a given Python object into the Axon envelope, applying token optimization and providing metrics.
*   **Request Body**: `TranslateOutRequest`
    ```json
    {
      "data": { /* Any JSON-serializable Python object */ },
      "session_id": "string", // Optional: for multi-turn optimization
      "target_model": "string" // Optional: e.g., "gpt-4o", "claude-3-opus-20240229" for accurate token estimation
    }
    ```
*   **Response**: Axon Envelope (see above)
*   **Status Codes**: `200 OK`, `422 Unprocessable Entity`

---

## 2. Proxy Endpoints (`/proxy` or `AXON_ROUTE_PREFIX_PROXY`)

### `POST /proxy/upstream`

*   **Description**: Forwards an HTTP request to an external upstream URL, captures its response, and returns it in an Axon envelope with token optimization. This is the easiest way to integrate Axon without modifying existing services.
*   **Security**: Subject to API key authentication and domain allowlisting.
*   **Request Body**: `UpstreamProxyRequest`
    ```json
    {
      "upstream_url": "string", // Required: The full URL of the upstream API
      "method": "string",       // Required: HTTP method (GET, POST, PUT, PATCH, DELETE)
      "headers": { "string": "string" }, // Optional: Custom headers for the upstream request
      "data": { /* Any JSON-serializable data */ }, // Optional: Request body for POST/PUT/PATCH
      "session_id": "string",   // Optional: for multi-turn optimization
      "timeout_seconds": 30     // Optional: Timeout for the upstream request
    }
    ```
*   **Response**: Axon Envelope, with an additional `upstream` field:
    ```json
    {
      "compact_text": "...",
      "metrics": { "..." },
      "upstream": {
        "url": "string",
        "method": "string",
        "status": "integer",
        "content_type": "string"
      }
    }
    ```
*   **Status Codes**: `200 OK` (upstream success), `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `502 Bad Gateway` (upstream connection failed), `422 Unprocessable Entity`

---

## 3. Process Endpoints (`/process` or `AXON_ROUTE_PREFIX_PROCESS`)

### `POST /process`

*   **Description**: Processes an inbound payload through a specified internal handler function and returns the *optimized inbound payload* along with the handler's result. This is useful for integrating Axon as a library within your application's logic.
*   **Request Body**: `ProcessRequest`
    ```json
    {
      "inbound": { /* Any JSON-serializable Python object */ }, // Required: The payload to process
      "handler": "string", // Required: Name of the handler (e.g., "echo", "my_custom_handler")
      "session_id": "string", // Optional: for multi-turn optimization
      "target_model": "string" // Optional: e.g., "gpt-4o", "claude-3-opus-20240229" for accurate token estimation
    }
    ```
*   **Response**: Axon Envelope, with an additional `handler_result` field:
    ```json
    {
      "compact_text": "...", // Optimized version of the 'inbound' payload
      "metrics": { "..." },
      "handler_result": { /* The output of the specified handler */ }
    }
    ```
*   **Status Codes**: `200 OK`, `400 Bad Request` (unsupported handler), `422 Unprocessable Entity`

---

## 4. Session Memory Endpoints (`/memory` or `AXON_ROUTE_PREFIX_MEMORY`)

These endpoints allow you to inspect and manage the persistent session state.

### `GET /memory/sessions`

*   **Description**: Lists all active session IDs currently tracked by Axon.
*   **Response**: `{"sessions": ["session-id-1", "session-id-2", ...]}`
*   **Status Codes**: `200 OK`

### `GET /memory/session/{session_id}`

*   **Description**: Retrieves detailed information and event history for a specific session.
*   **Path Parameters**:
    *   `session_id` (`string`): The ID of the session to retrieve.
*   **Query Parameters**:
    *   `limit` (`integer`, optional): Maximum number of events to return (default: 100).
*   **Response**: `{"session_id": "string", "created_at": "datetime", "last_accessed_at": "datetime", "events": [...]}`
*   **Status Codes**: `200 OK`, `404 Not Found`

### `DELETE /memory/session/{session_id}`

*   **Description**: Deletes all stored data (session state and events) for a specific session.
*   **Path Parameters**:
    *   `session_id` (`string`): The ID of the session to delete.
*   **Response**: `{"message": "Session <session_id> cleared."}`
*   **Status Codes**: `200 OK`

### `DELETE /memory/cleanup`

*   **Description**: Cleans up (deletes) all sessions that have not been accessed for a specified number of days.
*   **Query Parameters**:
    *   `days` (`integer`, optional): The age in days after which sessions should be deleted (default: 7).
*   **Response**: `{"message": "Cleaned up <count> old sessions."}`
*   **Status Codes**: `200 OK`

---

## 5. Security Endpoints (`/security` or `AXON_ROUTE_PREFIX_SECURITY`)

These endpoints allow dynamic management of Axon's security configuration.

### `GET /security/config`

*   **Description**: Retrieves the current security configuration (API key requirement, allowed domains, etc.).
*   **Response**: `{"require_api_key": "boolean", "allowed_domains": ["domain1", "domain2"], "allow_all_domains": "boolean"}`
*   **Status Codes**: `200 OK`

### `POST /security/domain/allow`
*   **Description**: Adds a domain to the allowlist.
*   **Query Parameters**: `domain` (`string`, required)

### `DELETE /security/domain`
*   **Description**: Removes a domain from the allowlist.
*   **Query Parameters**: `domain` (`string`, required)

### `POST /security/require-api-key`
*   **Description**: Toggles API key requirement.
*   **Query Parameters**: `required` (`boolean`, required)

### `POST /security/allow-all-domains`
*   **Description**: Toggles the "allow all domains" setting.
*   **Query Parameters**: `allow` (`boolean`, required)

*(For detailed usage of security endpoints, refer to Security Policy documentation.)*