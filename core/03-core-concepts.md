# Core Concepts

## Automatic Format Selection

Axon's core `TokenOptimizer` automatically benchmarks multiple encoding strategies for every payload and picks the one that produces the fewest tokens. This includes:

- **`graph`**: A highly compact format for code-like structures (symbols and edges).
- **`generic`**: A general-purpose compact format for any dictionary.
- **`json`**: The standard baseline.

## Multi-Turn Session Optimization (TOON & TRON)

For multi-turn conversations, Axon uses session-based strategies to achieve even greater savings:

- **TRON (Token-Reduced Object Notation)**: In a session, Axon remembers previously seen symbols or values and replaces them with short references (e.g., `@1`) on subsequent turns. Implemented via the `gcf_session` and `gcf_generic_session` strategies.
- **TOON (Token-Oriented Object Notation)**: Axon sends only the *changes* (a "delta") from the previous turn, rather than the full payload. Implemented via the `graph_delta` and `generic_delta` strategies.

You can see this in action by running the session benchmark:

```bash
python bridge/examples/session_benchmark.py
```

## Graph Profile Auto-Detection

If your payload contains a `symbols` key, the bridge automatically uses the **graph profile** instead of generic encoding:

```json
{
  "symbols": [
    {"name": "ServiceA", "module": "api", "type": "class"},
    {"name": "ServiceB", "module": "api", "type": "class"}
  ],
  "edges": [
    {"from": "ServiceA", "to": "ServiceB", "type": "calls"}
  ]
}
```

## Session Memory & Persistence

Persistent SQLite-backed memory tracks sessions, cached symbols, and event history:

```bash
# List all active sessions
curl http://127.0.0.1:8080/memory/sessions

# Get session details and event history
curl http://127.0.0.1:8080/memory/session/chat-42?limit=50

# Clean up sessions older than 7 days
curl -X DELETE http://127.0.0.1:8080/memory/cleanup?days=7
```

Memory automatically logs:
- Process calls and handlers invoked
- Upstream proxy calls and response status