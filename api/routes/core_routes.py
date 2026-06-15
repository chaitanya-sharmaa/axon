"""Core endpoints: health check, translate_in, translate_out."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Body

from domain.api_models import TranslateOutRequest, HealthResponse
from core.app_config import bridge


router = APIRouter(tags=["core"])


@router.get("/health", response_model=HealthResponse)
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@router.post("/translate/in")
async def translate_in(payload: Any = Body(...)) -> dict[str, Any]:
    """Normalize input to object format."""
    return {"object": bridge.from_any_to_object(payload)}


@router.post("/translate/out")
async def translate_out(req: TranslateOutRequest) -> dict[str, Any]:
    """Convert output to GCF envelope with token metrics."""
    return bridge.convert_output(req.data, session_id=req.session_id)
