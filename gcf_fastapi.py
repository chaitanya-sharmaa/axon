"""Backward-compatible entrypoint.

Prefer using `app.py` directly. This file exists to keep older startup commands working.
"""

from app import app, create_app

__all__ = ["app", "create_app"]
