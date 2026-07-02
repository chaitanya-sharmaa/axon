# Contributing to Axon Bridge

Thank you for taking the time to contribute! 🎉 Axon Bridge is designed to be a lightweight, token-saving middleware. We appreciate all PRs, from bug fixes to new compression strategies.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Setup](#development-setup)
3. [Running Tests & Linting (CI Requirements)](#running-tests--linting-ci-requirements)
4. [How to Add an Encoding Strategy](#how-to-add-an-encoding-strategy)
5. [Submitting a Pull Request](#submitting-a-pull-request)

---

## Prerequisites

- **Python 3.10+**
- **Node.js 20+** (only required if you are editing the `dashboard` UI)

---

## Development Setup

We use `pyproject.toml` as the single source of truth for dependencies.

1. Fork the repository and clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/axon.git
   cd axon
   ```

2. Create a virtual environment and install all dev dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev,redis,claude,langchain,lingua]"
   ```

3. Copy the env template and adjust as needed:
   ```bash
   cp .env.example .env
   ```

4. Start the server in hot-reload mode:
   ```bash
   axon serve --reload
   # or
   uvicorn app:app --reload --host 127.0.0.1 --port 8080
   ```

The interactive API docs are available at http://localhost:8080/docs.

---

## Running Tests & Linting (CI Requirements)

Axon uses GitHub Actions to run automated checks on every Pull Request. **Your PR will not be merged if these checks fail.** Please run them locally before pushing!

```bash
# 1. Run the full test suite
pytest tests/ -v

# 2. Lint (auto-fix where possible)
ruff check . --fix

# 3. Type check (Strict mode is enforced!)
mypy .
```

---

## How to Add an Encoding Strategy

Axon's token optimizer is designed to be extended. There are two ways to add a strategy:

### Option A — Built-in (core contribution)

1. Add a strategy constant in `services/token_optimizer.py`.
2. Add an encode block in `TokenOptimizer.optimize()`.
3. Add tests in `tests/test_token_optimizer.py`.

### Option B — Plugin (third-party, no fork needed)

```python
from services.plugin_registry import register_strategy

@register_strategy("my_brotli_strategy")
def encode_brotli(obj: Any, session_id: str | None = None) -> str:
    import brotli, json
    return brotli.compress(json.dumps(obj).encode()).hex()
```

---

## Submitting a Pull Request

1. Create a feature branch: `git checkout -b feat/my-new-feature`
2. Make your changes and add tests.
3. Run `pytest`, `ruff check .`, and `mypy .` to ensure CI will pass.
4. Push and open a PR against `main`. 
5. Fill out the provided PR template. If your PR fixes an issue, link it (e.g. `Fixes #12`).
