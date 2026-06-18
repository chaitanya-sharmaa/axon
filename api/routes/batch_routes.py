"""Batch processing endpoint — compress multiple payloads in one HTTP round-trip.

POST /batch
-----------
Request::

    {
      "requests": [
        {"payload": {...}, "session_id": "s1"},
        {"payload": {...}, "session_id": "s2"},
        ...
      ],
      "model": "gpt-4o"   // optional, for accurate token counting
    }

Response::

    {
      "results": [
        {"index": 0, "compact_text": "...", "metrics": {...}},
        ...
      ],
      "total_latency_ms": 42.1,
      "batch_size": 2
    }

All items in the batch are processed concurrently via ``asyncio.gather``.
The maximum batch size is controlled by ``AXON_BATCH_MAX_SIZE`` (default 50).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.app_config import axon_service

log = logging.getLogger(__name__)
router = APIRouter(tags=["batch"])

_MAX_BATCH = int(__import__("os").getenv("AXON_BATCH_MAX_SIZE", "50"))


class BatchItem(BaseModel):
    payload: Any
    session_id: str | None = None


class BatchRequest(BaseModel):
    requests: list[BatchItem] = Field(..., min_length=1)
    model: str | None = None


class BatchResultItem(BaseModel):
    index: int
    compact_text: str
    metrics: dict[str, Any]
    error: str | None = None


async def _process_item(index: int, item: BatchItem, model: str | None) -> BatchResultItem:
    try:
        envelope = axon_service.convert_output(
            item.payload, session_id=item.session_id, model=model
        )
        return BatchResultItem(
            index=index,
            compact_text=envelope["compact_text"],
            metrics=envelope["metrics"],
        )
    except Exception as exc:
        log.warning("Batch item %d failed: %s", index, exc)
        return BatchResultItem(
            index=index,
            compact_text="",
            metrics={},
            error=str(exc),
        )


@router.post("/batch")
async def batch_process(req: BatchRequest) -> dict[str, Any]:
    """Process multiple payloads concurrently and return all compressed results."""
    if len(req.requests) > _MAX_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size {len(req.requests)} exceeds maximum of {_MAX_BATCH}. "
                   f"Set AXON_BATCH_MAX_SIZE to increase the limit.",
        )

    t0 = time.monotonic()
    tasks = [_process_item(i, item, req.model) for i, item in enumerate(req.requests)]
    results = await asyncio.gather(*tasks)
    elapsed_ms = round((time.monotonic() - t0) * 1000, 2)

    return {
        "results": [r.model_dump() for r in results],
        "batch_size": len(results),
        "total_latency_ms": elapsed_ms,
        "errors": sum(1 for r in results if r.error),
    }
