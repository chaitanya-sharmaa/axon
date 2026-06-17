# Extending Axon

Axon is designed with modularity in mind, allowing you to extend its capabilities by adding new encoding strategies, integrating different memory stores, or defining custom handlers.

## 1. Adding New Token Optimization Strategies

The `TokenOptimizer` is the central place for new compression techniques.

**Steps:**

1.  **Define a new strategy name**: Add a new constant to `bridge/services/token_optimizer.py` (e.g., `STRATEGY_MY_NEW_COMPRESSION`).
2.  **Implement the encoding logic**:
    *   Create a new helper function (e.g., `_encode_my_new_compression(obj, session_state)`) that takes the normalized Python object and any necessary session state, and returns the compressed string.
    *   This function should ideally use a dedicated compression library or custom logic.
3.  **Integrate into `TokenOptimizer.optimize()`**:
    *   In the `optimize` method, add a new `if` block for your strategy.
    *   Call your encoding helper function.
    *   Use `_add(STRATEGY_MY_NEW_COMPRESSION, encoded_text)` to add the result to the list of candidates.
    *   Ensure you handle `session_id` and `payload_type` (graph/generic) appropriately if your strategy is session-aware or type-specific.
4.  **Update `ALL_STRATEGIES`**: Add your new strategy name to the `ALL_STRATEGIES` list in `token_optimizer.py`.
5.  **Add Tests**: Write unit tests in `bridge/services/test_token_optimizer.py` to verify your new strategy works correctly and wins when it should.
6.  **Document**: Update `docs/02-token-optimization-strategies.md` to describe your new strategy.

**Example (Conceptual):**

```python
# bridge/services/token_optimizer.py
STRATEGY_MY_NEW_COMPRESSION = "my_new_compression"
ALL_STRATEGIES.append(STRATEGY_MY_NEW_COMPRESSION)

def _encode_my_new_compression(obj: Any) -> str:
    # Your custom compression logic here
    return f"MYCOMPRESS:{json.dumps(obj['data'])}"

class TokenOptimizer:
    # ...
    def optimize(self, obj: Any, session_id: str | None = None, model: str | None = None, enabled_strategies: list[str] | None = None) -> OptimizerResult:
        # ... existing strategies ...
        if STRATEGY_MY_NEW_COMPRESSION in active:
            try:
                encoded = _encode_my_new_compression(obj)
                _add(STRATEGY_MY_NEW_COMPRESSION, encoded)
            except Exception as e:
                logging.warning(f"Strategy {STRATEGY_MY_NEW_COMPRESSION} failed: {e}")
        # ... rest of optimize method ...
```

## 2. Integrating Different Memory Stores

Axon currently uses `SqliteMemoryStore`. You can replace or augment this with other persistence layers (e.g., Redis, PostgreSQL) by implementing a new memory store class.

**Steps:**

1.  **Define an Interface**: Create an abstract base class (ABC) in `bridge/services/memory_store.py` (if one doesn't exist) that defines the methods your memory store must implement (e.g., `create_session`, `log_event`, `get_session_events`, `clear_session`, `cleanup_sessions`).
2.  **Implement Your Store**: Create a new class (e.g., `RedisMemoryStore`) that inherits from this ABC and implements all required methods using your chosen technology.
3.  **Update `core/app_config.py`**: Modify the `memory_store` singleton instantiation to use your new class instead of `SqliteMemoryStore`. You might need to add new environment variables in `core/settings.py` for your store's configuration (e.g., Redis connection string).
4.  **Update API Routes**: Ensure any API routes directly interacting with `memory_store` are compatible with your new store's methods.
5.  **Add Tests**: Write unit tests for your new memory store.
6.  **Document**: Update `docs/03-session-management.md` to mention your new memory store option.

## 3. Adding Custom Handlers

Handlers are functions that process the normalized input payload. You can add your own custom business logic.

**Steps:**

1.  **Create Your Handler Function**: In `bridge/domain/process_handlers.py`, define a new function that takes a Python object (the normalized payload) and returns a Python object (the processed result).
2.  **Register Your Handler**: Add your new function to the `_HANDLERS` dictionary in `bridge/domain/process_handlers.py`. The key will be the name used in the `/process` API endpoint.
3.  **Use Your Handler**: Call your handler via the `/process` API endpoint using its registered name.

**Example:**

```python
# bridge/domain/process_handlers.py
def my_custom_handler(payload: dict) -> dict:
    # Your custom logic here
    return {"processed_data": payload, "status": "custom_done"}

_HANDLERS = {
    "echo": echo_handler,
    "my_custom_handler": my_custom_handler, # Register your handler
}
```