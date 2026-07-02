"""Core endpoints: health (liveness + readiness), translate_in, translate_out."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from core.app_config import axon_service, memory_store
from domain.api_models import HealthResponse, TranslateOutRequest

log = logging.getLogger(__name__)
router = APIRouter(tags=["core"])


# ── Health checks ──────────────────────────────────────────────────────────────

@router.get("/health/live", response_model=HealthResponse, summary="Liveness probe")
async def health_live() -> dict:
    """Kubernetes liveness probe — returns 200 if the process is running."""
    return {"status": "ok"}


@router.get("/health/ready", response_model=HealthResponse, summary="Readiness probe")
async def health_ready() -> dict:
    """Kubernetes readiness probe — returns 200 only if the DB connection is healthy.

    Returns 503 if the persistent memory store is unavailable.
    """
    try:
        # Verify the DB is reachable by running a lightweight query
        await memory_store.session_exists("__healthcheck__")
    except Exception as exc:
        log.error("Readiness check failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Memory store unavailable: {exc}",
        )
    return {"status": "ok"}


# Keep the legacy /health endpoint for backward compatibility
@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health_legacy() -> dict:
    return {"status": "ok"}


# ── Translation utilities ──────────────────────────────────────────────────────

@router.post("/translate/in", summary="Decode any format to Python object")
async def translate_in(payload: Any = Body(...)) -> dict[str, Any]:
    """Normalize any input (JSON string, Axon text, dict) to a Python object."""
    return {"object": axon_service.from_any_to_object(payload)}


@router.post("/translate/out", summary="Encode object to Axon envelope")
async def translate_out(req: TranslateOutRequest) -> dict[str, Any]:
    """Convert a Python object to the Axon compact envelope with token metrics."""
    return axon_service.convert_output(req.data, session_id=req.session_id)
