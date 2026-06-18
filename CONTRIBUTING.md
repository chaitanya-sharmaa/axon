# Contributing to Axon Bridge

Thank you for taking the time to contribute! 🎉

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Running Tests](#running-tests)
4. [Code Style](#code-style)
5. [How to Add an Encoding Strategy](#how-to-add-an-encoding-strategy)
6. [Submitting a Pull Request](#submitting-a-pull-request)
7. [Reporting Bugs](#reporting-bugs)

---

## Getting Started

1. Fork the repository and clone your fork:
   ```bash
   git clone https://github.com/your-username/axon-bridge.git
   cd axon-bridge/bridge
   ```

2. Create a virtual environment and install all dev dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev,redis,claude,langchain]"
   ```

3. Copy the env template and adjust as needed:
   ```bash
   cp .env.example .env
   ```

---

## Development Setup

Start the server in hot-reload mode:
```bash
axon serve --reload
# or
uvicorn app:app --reload --host 127.0.0.1 --port 8080
```

The interactive API docs are available at http://localhost:8080/docs.

---

## Running Tests

```bash
# Run the full test suite
pytest tests/ -v

# Run a single test file
pytest tests/test_token_optimizer.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

### Linting & Type Checking

```bash
# Lint (auto-fix where possible)
ruff check . --fix

# Type check
mypy . --ignore-missing-imports
```

---

## Code Style

- **Formatter**: `ruff format` (Black-compatible)
- **Linter**: `ruff check`
- **Type hints**: all public functions must have full type annotations
- **Docstrings**: Google-style for public classes and functions
- **Line length**: 100 characters

Pre-commit hooks (optional but recommended):
```bash
pip install pre-commit
pre-commit install
```

---

## How to Add an Encoding Strategy

Axon's token optimizer is designed to be extended. There are two ways to add a strategy:

### Option A — Built-in (core contribution)

1. Add a strategy constant in `services/token_optimizer.py`:
   ```python
   STRATEGY_MY_STRATEGY = "my_strategy"
   ALL_STRATEGIES = [..., STRATEGY_MY_STRATEGY]
   ```

2. Add an encode block in `TokenOptimizer.optimize()`:
   ```python
   if STRATEGY_MY_STRATEGY in active:
       try:
           _add(STRATEGY_MY_STRATEGY, my_encoder(obj))
       except Exception as e:
           logging.warning(f"Strategy {STRATEGY_MY_STRATEGY} failed: {e}")
   ```

3. Add tests in `tests/test_token_optimizer.py`.

### Option B — Plugin (third-party, no fork needed)

```python
from services.plugin_registry import register_strategy

@register_strategy("my_brotli_strategy")
def encode_brotli(obj: Any, session_id: str | None = None) -> str:
    import brotli, json
    return brotli.compress(json.dumps(obj).encode()).hex()
```

Then include your module in your app's startup code.

---

## Submitting a Pull Request

1. Create a feature branch:
   ```bash
   git checkout -b feat/my-new-feature
   ```

2. Make your changes, add tests, update `CHANGELOG.md` under `[Unreleased]`.

3. Ensure all checks pass:
   ```bash
   pytest tests/ -v
   ruff check .
   mypy . --ignore-missing-imports
   ```

4. Push and open a PR against `main`. Fill in the PR template.

### PR Checklist

- [ ] Tests added / updated for all changed behaviour
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] All existing tests pass
- [ ] Type annotations added for new public functions
- [ ] Docstrings updated

---

## Reporting Bugs

Please open a GitHub Issue with:
- Axon version (`axon --version` or from `pyproject.toml`)
- Python version
- Minimal reproducible example
- Expected vs actual behaviour
- Relevant log output (use `AXON_LOG_FORMAT=json AXON_LOG_LEVEL=DEBUG`)
