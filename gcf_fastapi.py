"""Backward-compatible entrypoint within the bridge package.

This file re-exports the FastAPI application from `bridge.app`.
The primary entrypoint is `app.py` at the project root.
"""

from .app import app, create_app

__all__ = ["app", "create_app"]
