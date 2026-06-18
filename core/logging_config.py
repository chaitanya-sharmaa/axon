"""Structured logging configuration for Axon Bridge.

Set ``AXON_LOG_FORMAT=json`` for machine-readable output (Datadog, Splunk,
CloudWatch).  Defaults to the standard human-readable format.

Usage
-----
Call ``configure_logging()`` once at application startup (done automatically
by ``create_app()`` in ``app.py``).

Every log record automatically includes:
- ``request_id`` — injected by ``RequestIDMiddleware`` via ``contextvars``
- ``ts``          — ISO-8601 UTC timestamp
- ``level``       — log level name
- ``logger``      — logger name
- ``msg``         — log message
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# Context variable set by RequestIDMiddleware on each request
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class _JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get("-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_format: str = "text", log_level: str = "INFO") -> None:
    """Configure root logger.

    Parameters
    ----------
    log_format:
        ``"json"`` for structured JSON output, anything else for plain text.
    log_level:
        Standard Python log-level string (``"DEBUG"``, ``"INFO"``, ``"WARNING"``…).
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if log_format.lower() == "json":
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s (%(request_id)s): %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%SZ",
            )
        )

    # Inject request_id into every log record via a filter
    class _RequestIDFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            record.request_id = request_id_var.get("-")  # type: ignore[attr-defined]
            return True

    handler.addFilter(_RequestIDFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
