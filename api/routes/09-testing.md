# Testing Axon

Axon uses `pytest` for its unit and integration tests. This document outlines how to run the tests and what each test file covers.

## Running Tests

To run all tests, navigate to the project root directory and execute:

```bash
pytest
```

To run tests with verbose output and coverage reporting:

```bash
pytest --verbose --cov=bridge --cov-report=term-missing
```

## Test Files Overview

### `bridge/services/test_token_optimizer.py`

This file contains the core unit tests for the `TokenOptimizer` service. It verifies:

*   **Generic Payloads**:
    *   First-turn optimization (choosing `generic`).
    *   `generic_delta` (TOON) winning when only a few fields change.
    *   `generic_session` (TRON) winning when scalar values are repeated.
    *   `schema_values` winning for flat, repetitive data.
*   **Graph Payloads**:
    *   First-turn optimization (choosing `graph`).
    *   `graph_delta` (TOON) winning when symbols/edges are added.
    *   `graph_session` (TRON) winning when symbols are repeated.
*   **Session Management**:
    *   `clear_session` correctly resets state.
    *   Unified session management between `AxonService` and `TokenOptimizer`.
*   **Storage Backends**:
    *   Verifies logic across both `SqliteMemoryStore` and `RedisMemoryStore`.
*   **Edge Cases**: Handling of empty graph payloads.

### `bridge/api/routes/test_*.py` (if present)

These files would contain integration tests for the FastAPI endpoints, ensuring that requests are routed correctly, security policies are enforced, and responses are formatted as expected. (Currently, these might be covered by manual debug scripts or are yet to be formalized).